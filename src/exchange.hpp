// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

void buck::exchange(const name& account, const asset quantity) {
  require_auth(account);
  
  check(check_operation_status(5), "exchange has been temporarily frozen");
  check(quantity.is_valid(), "invalid quantity");
  check(quantity.amount > 0, "must transfer positive quantity");
  check(quantity.symbol == BUCK || quantity.symbol == EOS, "symbol mismatch");
  
  // create accounts if not yet
  add_balance(account, ZERO_BUCK, account);
  add_exchange_funds(account, ZERO_EOS, account);
  
  // take tokens
  if (quantity.symbol == BUCK) {
    check(quantity.amount >= 25'0000, "minimum amount is 25 BUCK");
    sub_balance(account, quantity);
  }
  else {
    check(quantity.amount >= 5'0000, "minimum amount is 5 EOS");
    sub_exchange_funds(account, quantity);
  }
  
  const auto ex_itr = _exchange.find(account.value);
  if (ex_itr == _exchange.end()) {
    
    // new order
    _exchange.emplace(account, [&](auto& r) {
      r.account = account;
      r.quantity = quantity;
      r.timestamp = get_current_time_point();
    });
  }
  else {
    
    if (ex_itr->quantity.symbol != quantity.symbol) {
      
      // return previous order
      if (ex_itr->quantity.symbol == BUCK) {
        add_balance(account, ex_itr->quantity, account);
      }
      else {
        add_exchange_funds(account, ex_itr->quantity, account);
      }
      
      // setup new one
      _exchange.modify(ex_itr, account, [&](auto& r) {
        r.quantity = quantity;
        r.timestamp = get_current_time_point();
      });
    }
    else {
      
      // update existing
      _exchange.modify(ex_itr, account, [&](auto& r) {
        r.quantity += quantity;
        r.timestamp = get_current_time_point();
      });
    }
  }
  run(10);
}

void buck::run_exchange(uint8_t max) {
  if (!check_operation_status(5)) return;
  
  const uint32_t price = get_eos_usd_price();
  const time_point oracle_timestamp = _stat.begin()->oracle_timestamp;
  
  uint8_t processed = 0;
  auto index = _exchange.get_index<"type"_n>();
  
  while (index.begin() != index.end() && max > processed) {
    processed++;
    
    // get elements
    const auto buy_itr = index.begin();
    const auto sell_itr = --index.end(); // take first from end
    
    // ran out of sellers or buyers
    if (buy_itr->quantity.symbol == BUCK || sell_itr->quantity.symbol == EOS) return;
    
    // no sell or buy orders made since the last oracle update
    if (buy_itr->timestamp > oracle_timestamp || sell_itr->timestamp > oracle_timestamp) return;
    
    // proceed
    const int64_t buck_amount = std::min(sell_itr->quantity.amount * 100, buy_itr->quantity.amount * price);
    const int64_t eos_amount = buck_amount / price;
    
    const asset buck = asset(buck_amount / 100, BUCK);
    const asset eos = asset(eos_amount, EOS);
    
    // update balances
    add_balance(sell_itr->account, buck, same_payer);
    add_exchange_funds(buy_itr->account, eos, same_payer);
    
    // update orders
    if (sell_itr->quantity.amount == buck.amount) {
      index.erase(sell_itr);
    }
    else {
      index.modify(sell_itr, same_payer, [&](auto& r) {
        r.quantity -= buck;  
      });
    }
    
    if (buy_itr->quantity.amount == eos_amount) {
      index.erase(buy_itr);
    }
    else {
      index.modify(buy_itr, same_payer, [&](auto& r) {
        r.quantity -= eos;
      });
    }
  }
}