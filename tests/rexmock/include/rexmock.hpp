// Copyright © Scruge 2019.
// This file is part of Buck Protocol.
// Created by Yaroslav Erohin.

#include <eosio/eosio.hpp>
#include <eosio/print.hpp>
#include <eosio/asset.hpp>
#include <eosio/asset.hpp>

#include <string>
#include <deque>

using namespace eosio;

CONTRACT rexmock : public contract {
  
  public:
    using contract::contract;
    rexmock(eosio::name receiver, eosio::name code, datastream<const char*> ds):contract(receiver, code, ds) {}

    ACTION deposit( const name& owner, const asset& amount );
    
    ACTION withdraw( const name& owner, const asset& amount );
    
    ACTION buyrex( const name& from, const asset& amount );
    
    ACTION sellrex( const name& from, const asset& rex );
    
    ACTION resetstat();

  private:
  
    TABLE stats {
      uint64_t eos_price;
      
      uint64_t primary_key() const { return 0; }
    };
    
    typedef eosio::multi_index< "rexstat"_n, stats > stats_table;
  
    TABLE rex_balance {
      uint8_t version = 0;
      name    owner;
      asset   vote_stake; /// the amount of CORE_SYMBOL currently included in owner's vote
      asset   rex_balance; /// the amount of REX owned by owner
      int64_t matured_rex = 0; /// matured REX available for selling
      std::deque<std::pair<time_point_sec, int64_t>> rex_maturities; /// REX daily maturity buckets
    
      uint64_t primary_key() const { return owner.value; }
    };
    
    typedef eosio::multi_index< "rexbal"_n, rex_balance > rex_balance_table;
    
    TABLE rex_fund {
      uint8_t version = 0;
      name    owner;
      asset   balance;
    
      uint64_t primary_key() const { return owner.value; }
    };
    
    typedef eosio::multi_index< "rexfund"_n, rex_fund > rex_fund_table;
    
    uint64_t get_eos_price();
};