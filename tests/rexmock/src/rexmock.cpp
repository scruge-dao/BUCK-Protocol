// Copyright © Scruge 2019.
// This file is part of Buck Protocol.
// Created by Yaroslav Erohin.

#include <rexmock.hpp>

const uint64_t eos_price = 1000; // in REX
const double dividends_multiplier = 1.01;

ACTION rexmock::resetstat() {
  stats_table _stat(_self, _self.value);
  if (_stat.begin() != _stat.end()) {
    _stat.erase(_stat.begin());
  }
}

ACTION rexmock::deposit( const name& owner, const asset& amount ) {
  // eosio::print("deposit: "); eosio::print(amount); eosio::print("\n");
  
  check(amount.amount > 0, "can not deposit negative amount");
  rex_fund_table _rexfunds(_self, _self.value);
  auto itr = _rexfunds.find( owner.value );
  if ( itr == _rexfunds.end() ) {
     _rexfunds.emplace( _self, [&]( auto& fund ) {
        fund.owner   = owner;
        fund.balance = amount;
     });
  } else {
     _rexfunds.modify( itr, same_payer, [&]( auto& fund ) {
        fund.balance += amount;
     });
  }
}

ACTION rexmock::withdraw( const name& owner, const asset& amount ) {
  // eosio::print("withdraw: "); eosio::print(amount); eosio::print("\n");
  
  check(amount.amount > 0, "can not withdraw negative amount");
  rex_fund_table _rexfunds(_self, _self.value);
  auto itr = _rexfunds.require_find( owner.value, "must deposit to REX fund first" );
  check(itr->balance >= amount, "overdrawn deposit balance");
  _rexfunds.modify( itr, same_payer, [&]( auto& fund ) {
     fund.balance -= amount;
  });
}

ACTION rexmock::buyrex( const name& from, const asset& amount ) {
  // eosio::print("buy: "); eosio::print(amount); eosio::print("\n");
  
  check(amount.amount > 0, "can not buy negative amount");
  rex_balance_table _rexbalance(_self, _self.value);
  auto bitr = _rexbalance.find( from.value );
  if ( bitr == _rexbalance.end() ) {
     bitr = _rexbalance.emplace( _self, [&]( auto& rb ) {
        rb.owner       = from;
        rb.rex_balance = asset(amount.amount * get_eos_price(), eosio::symbol{"REX", 4});
     });
  } else {
     _rexbalance.modify( bitr, same_payer, [&]( auto& rb ) {
        rb.rex_balance.amount += amount.amount * get_eos_price();
     });
  }
  
  withdraw(from, amount);
}

ACTION rexmock::sellrex( const name& from, const asset& rex ) {
  // eosio::print("sell: "); eosio::print(rex); eosio::print("\n");
  
  check(rex.amount > 0, "can not sell negative amount");
  rex_balance_table _rexbalance(_self, _self.value);
  auto bitr = _rexbalance.require_find( from.value, "must buy some REX first" );
  check(bitr->rex_balance >= rex, "overdrawn REX balance");
  
  _rexbalance.modify( bitr, same_payer, [&]( auto& rb ) {
    rb.rex_balance.amount -= rex.amount;
  });
  
  deposit(from, asset(rex.amount * dividends_multiplier / get_eos_price(), eosio::symbol{"EOS", 4}));
}

uint64_t rexmock::get_eos_price() {
  stats_table _stat(_self, _self.value);
  if (_stat.begin() != _stat.end()) {
    _stat.modify(_stat.begin(), same_payer, [&](auto& r) {
      r.eos_price -= 1;
    });
  }
  else {
    _stat.emplace(_self, [&](auto& r) {
      r.eos_price = eos_price;
    });
  }
  auto price = _stat.begin()->eos_price;
  // eosio::print("eos price: "); eosio::print(price); eosio::print("\n");
  return price;
}
