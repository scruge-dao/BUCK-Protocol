// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

#if DEBUG
#define PRINT(x, y) { eosio::print(x); eosio::print(": "); eosio::print(y); eosio::print("\n"); }
#define PRINT_(x) { eosio::print(x); eosio::print("\n"); }
#define RMS(x, scope) { x table(_self, scope); auto item = table.begin(); while (item != table.end()) item = table.erase(item); }
#define RM(x) { x table(_self, _self.value); auto item = table.begin(); while (item != table.end()) item = table.erase(item); }

void buck::zdestroy() {
  RM(processing_i)
  RM(redeem_req_i)
  RM(close_req_i)
  RM(reparam_req_i)
  RM(cdp_i)
  RM(fund_i)
  RM(taxation_i)
  
  RMS(stats_i, BUCK.code().raw())
  RMS(accounts_i, "yaroslaveroh"_n.value)
  RMS(accounts_i, "scrugeosbuck"_n.value)
  RMS(accounts_i, "testaccountp"_n.value)
  RMS(accounts_i, "equityscruge"_n.value)
  RMS(accounts_i, "user1"_n.value)
  RMS(accounts_i, "user2"_n.value)
  RMS(accounts_i, "user3"_n.value)
}
#else
#define PRINT(x, y) 
#define PRINT_(x)
#endif

#if TEST_TIME
void buck::zmaketime(int64_t seconds) {
  time_test_i _time(_self, _self.value);
  
  if (seconds < 0) {
    _time.erase(_time.begin());
    return;
  }
  
  if (_time.begin() != _time.end()) {
    _time.modify(_time.begin(), same_payer, [&](auto& r) {
      r.now = time_point(time_point_sec(seconds));
    });
  }
  else {
    _time.emplace(_self, [&](auto& r) {
      r.now = time_point(time_point_sec(seconds));
    });
  }
}
#endif