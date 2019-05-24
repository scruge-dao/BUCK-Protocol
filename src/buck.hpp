// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

CONTRACT buck : public contract {
  public:
    using contract::contract;
    buck(eosio::name receiver, eosio::name code, datastream<const char*> ds);
    
    // user
    ACTION withdraw(const name& account, const asset& quantity);
    ACTION open(const name& account, const asset& quantity, uint16_t dcr, uint16_t icr);
    ACTION change(uint64_t cdp_id, const asset& change_debt, const asset& change_collateral);
    ACTION changeicr(uint64_t cdp_id, uint16_t icr);
    ACTION close(uint64_t cdp_id);
    ACTION redeem(const name& account, const asset& quantity);
    ACTION transfer(const name& from, const name& to, const asset& quantity, const std::string& memo);
    ACTION save(const name& account, const asset& quantity);
    ACTION unsave(const name& account, const uint64_t quantity);
    ACTION exchange(const name& account, const asset quantity);
    ACTION freeram(const name& account);
    ACTION cancelorder(const name& account);
    ACTION removedebt(uint64_t cdp_id);
    ACTION run(uint8_t max);
    
    // admin
    ACTION setoperation(uint8_t level);
    ACTION update(uint32_t eos_price);
    ACTION forceupdate(uint32_t eos_price);
    ACTION processrex();
  
    #if TEST_TIME
    ACTION zmaketime(int64_t seconds);
    #endif
    
    #if DEBUG
    ACTION zdestroy();
    #endif
    
    [[eosio::on_notify("eosio.token::transfer")]]
    void notify_transfer(const name& from, const name& to, const asset& quantity, const std::string& memo);
    
  private:
    
    enum LiquidationStatus: uint8_t { liquidation_complete = 0, failed = 1, processing_liquidation = 2 }; 
    
    enum ProcessingStatus: uint8_t { processing_complete = 0, processing_redemption_requests = 1, processing_cdp_requests = 2 };

    TABLE account {
      asset     balance;
    
      uint64_t primary_key() const { return balance.symbol.code().raw(); }
    };
    
    TABLE currency_stats {
      asset       supply;
      asset       max_supply;
      name        issuer;
      
      // oracle updates
      time_point  oracle_timestamp;
      uint32_t    oracle_eos_price;
      
      // 2 bits for liquidation status
      // 2 bits for requests status
      uint8_t     processing_status;
      
      // restriction bitmask
      // 0 - cdp operations
      // 1 - liquidation processing
      // 2 - deposit/withdraw (rex)
      // 3 - transfer
      // 4 - price update
      // 5 - exchange
      // 6 - tax processing
      // 7 - savings operations
      uint8_t     operation_status;
      
      uint64_t primary_key() const { return supply.symbol.code().raw(); }
    };
    
    TABLE taxation_stats {
      
      // insurance
      asset       insurance_pool;
      asset       collected_excess;  // BUCK this round
      uint64_t    total_excess;
      uint128_t   aggregated_excess;
      
      // savings
      asset       savings_pool;      // saved + proceeds
      asset       collected_savings; // REX this round
      uint64_t    savings_supply;    // virtual toke
      
      uint64_t primary_key() const { return 0; }
    };
    
    TABLE close_req {
      uint64_t    cdp_id;
      asset       debt;
      name        account;
      time_point  timestamp;
      
      uint64_t primary_key() const { return cdp_id; }
    };
    
    TABLE fund {
      name      account;
      asset     balance;          // REX
      asset     exchange_balance; // EOS
      int64_t  savings_balance;  // virtual toke
      
      int64_t  matured_rex;
      std::deque<std::pair<time_point_sec, int64_t>> rex_maturities;
      
      uint64_t primary_key() const { return account.value; }
    };
    
    TABLE redeem_req {
      name        account;
      asset       quantity;
      time_point  timestamp;
      
      uint64_t primary_key() const { return account.value; }
    };
    
    TABLE reparam_req {
      uint64_t        cdp_id;
      asset           change_collateral;
      asset           change_debt;
      name            account;
      time_point      timestamp;
      time_point_sec  maturity;
      
      uint64_t primary_key() const { return cdp_id; }
    };
    
    struct processing {
      asset current_balance;
      name  account;
      
      uint64_t primary_key() const { return 0; }
    };
    
    TABLE order {
      name        account;
      asset       quantity;
      time_point  timestamp;
      
      uint64_t primary_key() const { return account.value; }
      
      uint64_t by_type() const {
        
        const uint32_t seconds = time_point_sec(timestamp).utc_seconds;
        
        // buyers
        if (quantity.symbol == EOS) return seconds;
        
        // sellers
        return UINT64_MAX - seconds;
      }
    };
    
    TABLE cdp {
      uint64_t        id;
      uint16_t        icr;
      name            account;
      asset           debt;
      asset           collateral;
      uint32_t        modified_round; // adcrual round
      time_point_sec  maturity;       // maturity of REX collateral
      
      #if DEBUG
      void p() const {
        eosio::print("#");eosio::print(id);
        eosio::print(" c: ");eosio::print(collateral);
        eosio::print(" d: ");eosio::print(debt);
        eosio::print(" icr: ");eosio::print(icr);
        eosio::print(" time: ");eosio::print(modified_round);
        eosio::print("\n");
      }
      #endif
      
      uint64_t primary_key() const { return id; }
      uint64_t by_account() const { return account.value; }
      
      uint64_t by_accrued_time() const { 
        
        if (debt.amount == 0 || collateral.amount == 0) return UINT64_MAX;
        
        return modified_round;
      }
      
      // index to search for liquidators with the highest ability to bail out bad debt
      double liquidator() const {
        
        if (icr == 0 || collateral.amount == 0) return std::numeric_limits<double>::infinity(); // end of the table
        
        if (debt <= MIN_DEBT && collateral > MIN_INSURER_REX) 
          return double(icr) / double(collateral.amount); // descending c/icr

        const double cd = double(collateral.amount) / double(debt.amount);
        return MAX_ICR / MIN_COLLATERAL.amount + 1 + icr / cd; // descending cd/icr
      }
      
      // index to search for debtors with lowest dcr
      double debtor() const {
        
        if (debt.amount == 0 || collateral.amount == 0) return std::numeric_limits<double>::infinity(); // end of the table
        
        const double cd = double(collateral.amount) / double(debt.amount);
        return cd; // ascending cd
      }
    };
    
    typedef multi_index<"accounts"_n, account> accounts_i;
    typedef multi_index<"stat"_n, currency_stats> stats_i;
    typedef multi_index<"fund"_n, fund> fund_i;
    typedef multi_index<"taxation"_n, taxation_stats> taxation_i;
    
    typedef multi_index<"closereq"_n, close_req> close_req_i;
    typedef multi_index<"reparamreq"_n, reparam_req> reparam_req_i;
    typedef multi_index<"redeemreq"_n, redeem_req> redeem_req_i;
    
    typedef multi_index<"process"_n, processing> processing_i;
    
    typedef multi_index<"cdp"_n, cdp,
      indexed_by<"debtor"_n, const_mem_fun<cdp, double, &cdp::debtor>>,
      indexed_by<"liquidator"_n, const_mem_fun<cdp, double, &cdp::liquidator>>,
      indexed_by<"accrued"_n, const_mem_fun<cdp, uint64_t, &cdp::by_accrued_time>>,
      indexed_by<"byaccount"_n, const_mem_fun<cdp, uint64_t, &cdp::by_account>>
        > cdp_i;
    
    typedef multi_index<"exchange"_n, order,
      indexed_by<"type"_n, const_mem_fun<order, uint64_t, &order::by_type>>
        > exchange_i;
    
    // rex 
    
    struct rex_fund {
      uint8_t version = 0;
      name    owner;
      asset   balance;

      uint64_t primary_key() const { return owner.value; }
    };

    struct rex_balance {
      uint8_t version = 0;
      name    owner;
      asset   vote_stake; /// the amount of CORE_SYMBOL currently included in owner's vote
      asset   rex_balance; /// the amount of REX owned by owner
      int64_t matured_rex = 0; /// matured REX available for selling
      std::deque<std::pair<time_point_sec, int64_t>> rex_maturities; /// REX daily maturity buckets

      uint64_t primary_key() const { return owner.value; }
    };
    
    struct rex_pool {
      uint8_t    version;
      asset      total_lent; /// total amount of CORE_SYMBOL in open rex_loans
      asset      total_unlent; /// total amount of CORE_SYMBOL available to be lent (connector)
      asset      total_rent; /// fees received in exchange for lent  (connector)
      asset      total_lendable; /// total amount of CORE_SYMBOL that have been lent (total_unlent + total_lent)
      asset      total_rex; /// total number of REX shares allocated to contributors to total_lendable
      asset      namebid_proceeds; /// the amount of CORE_SYMBOL to be transferred from namebids to REX pool
      uint64_t   loan_num; /// increments with each new loan
      
      uint64_t primary_key() const { return 0; }
    };
  
    typedef multi_index<"rexbal"_n, rex_balance> rex_balance_i;
    typedef multi_index<"rexfund"_n, rex_fund> rex_fund_i;
    typedef multi_index<"rexpool"_n, rex_pool> rex_pool_i;
    
    // test time
    
    #if TEST_TIME
    TABLE time_test {
      time_point_sec now;
     
      uint64_t primary_key() const { return 0; }
    };
    
    typedef multi_index<"testtime"_n, time_test> time_test_i;
    #endif
    
    // methods
    
    bool init();
    void add_balance(const name& owner, const asset& value, const name& ram_payer);
    void sub_balance(const name& owner, const asset& value);
    void add_funds(const name& from, const asset& quantity, const name& ram_payer, time_point_sec maturity);
    time_point_sec sub_funds(const name& from, const asset& quantity);
    void add_exchange_funds(const name& from, const asset& quantity, const name& ram_payer);
    void sub_exchange_funds(const name& from, const asset& quantity);
    
    void process_taxes();
    void add_savings_pool(const asset& value);
    void accrue_interest(const cdp_i::const_iterator& cdp_itr, bool accrue_min);
    void set_excess_collateral(const cdp_i::const_iterator& cdp_itr);
    void remove_excess_collateral(const cdp_i::const_iterator& cdp_itr);
    void update_supply(const asset& quantity);
    void cancel_previous_requests(uint64_t cdp_id);
    
    void run_requests(uint8_t max);
    void run_liquidation(uint8_t max);
    void set_liquidation_status(LiquidationStatus status);
    void set_processing_status(ProcessingStatus status);
    
    void change(uint64_t cdp_id, const asset& change_debt, const asset& change_collateral, bool force_accrue);
    inline void inline_transfer(const name& account, const asset& quantity, const std::string& memo, const name& contract);
    
    void buy_rex(const name& account, const asset& quantity);
    void sell_rex(const name& account, const asset& quantity);
    void process_maturities(const fund_i::const_iterator& fund_itr);
    void run_exchange(uint8_t max);
    void collect_taxes(uint32_t max);
    void _update(uint32_t eos_price, bool force);
    
    // getters
    bool check_operation_status(uint8_t task_number) const;
    int64_t convert(uint128_t quantity, bool to_rex) const;
    int64_t to_buck(int64_t quantity) const;
    int64_t to_rex(int64_t quantity, int64_t tax) const;
    uint32_t get_eos_usd_price() const;
    asset get_rex_balance() const;
    asset get_eos_rex_balance() const;
    ProcessingStatus get_processing_status() const;
    LiquidationStatus get_liquidation_status() const;
    time_point get_current_time_point() const;
    time_point_sec current_time_point_sec() const;
    time_point_sec get_maturity() const;
    
    // tables
    cdp_i               _cdp;
    stats_i             _stat;
    taxation_i          _tax;
    fund_i              _fund;
    close_req_i         _closereq;
    reparam_req_i       _reparamreq;
    redeem_req_i        _redeemreq;
    processing_i        _process;
    exchange_i          _exchange;
};