// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

void buck::transfer(const name& from, const name& to, const asset& quantity, const std::string& memo) {
  require_auth(from);
  check(check_operation_status(3), "buck transfer has been temporarily frozen");
  
  check(from != to, "cannot transfer to self");
  check(is_account(to), "to account does not exist");
  
  require_recipient(from);
  require_recipient(to);
  
  check(quantity.is_valid(), "invalid quantity");
  check(quantity.amount > 0, "must transfer positive quantity");
  check(quantity.symbol == BUCK, "symbol precision mismatch");
  check(memo.size() <= 256, "memo has more than 256 bytes");

  const auto payer = has_auth(to) ? to : from;
  sub_balance(from, quantity);
  add_balance(to, quantity, payer);
  run(3);
}

void buck::withdraw(const name& account, const asset& quantity) {
  require_auth(account);
  check(check_operation_status(2), "deposit/withdraw operations have been temporarily frozen");
  
  check(quantity.symbol.is_valid(), "invalid quantity");
	check(quantity.amount > 0, "must transfer positive quantity");
  
  if (quantity.symbol == REX) {
    time_point_sec maturity_time = sub_funds(account, quantity);
    check(current_time_point_sec() > maturity_time, "insufficient matured rex");
    sell_rex(account, quantity);
  }
  else if (quantity.symbol == EOS) {
    sub_exchange_funds(account, quantity);
    inline_transfer(account, quantity, "buck: withdraw from exchange funds", EOSIO_TOKEN);
  }
  else {
    check(false, "symbol mismatch");
  }
  run(10);
}

void buck::notify_transfer(const name& from, const name& to, const asset& quantity, const std::string& memo) {
  require_auth(from);
  if (to != _self || from == _self || from == "eosio.rex"_n) { return; }
  
  check(_stat.begin() != _stat.end(), "contract is not yet initiated");
  check(check_operation_status(2), "deposit/withdraw operations have been temporarily frozen");
  
  check(quantity.symbol == EOS, "you have to transfer EOS");
  check(get_first_receiver() == "eosio.token"_n, "you have to transfer EOS");

  check(quantity.symbol.is_valid(), "invalid quantity");
	check(quantity.amount > 0, "must transfer positive quantity");
  
  if (memo == "deposit") {
    buy_rex(from, quantity);
  }
  else if (memo == "exchange") {
    add_exchange_funds(from, quantity, _self);
  }
  else {
    check(false, "do not send tokens in the contract without correct memo");
  }
  run(3);
}

void buck::freeram(const name& account) {
  require_auth(account);
  
  auto index = _cdp.get_index<"byaccount"_n>();
  auto cdp_itr = index.find(account.value);
  check(cdp_itr == index.end(), "you still have cdps opened");
  
  const auto fund_itr = _fund.find(account.value);
  if (fund_itr != _fund.end()) {
    check(fund_itr->balance.amount == 0, "you still have REX in your funds");
    check(fund_itr->exchange_balance.amount == 0, "you still have EOS in your exchange funds");
    _fund.erase(fund_itr);
  }
  
  accounts_i accounts(_self, account.value);
  const auto account_itr = accounts.find(BUCK.code().raw());
  if (account_itr != accounts.end()) {
    check(account_itr->balance.amount == 0, "you still have BUCK in your balance");
    accounts.erase(account_itr);
  }
  
  run(10);
}

void buck::open(const name& account, const asset& quantity, uint16_t dcr, uint16_t icr) {
  require_auth(account);
  check(check_operation_status(0), "cdp operations have been temporarily frozen");
  
  check(quantity.is_valid(), "invalid quantity");
  check(quantity.amount > 0, "can not use negative value");
  check(quantity.symbol == REX, "can not use asset with different symbol");
  
  check(dcr >= CR || dcr == 0, "dcr value is too small");
  check(icr >= CR || icr == 0, "icr value is too small");
  check(icr != 0 || dcr != 0, "icr and dcr can not be both 0");
  
  check(dcr <= MAX_ICR, "dcr value is too high");
  check(icr <= MAX_ICR, "icr value is too high");
  
  const time_point oracle_timestamp = _stat.begin()->oracle_timestamp;
  const uint32_t now = time_point_sec(oracle_timestamp).utc_seconds;
  auto issue_debt = ZERO_BUCK;
  
  const auto min_collateral = convert(MIN_COLLATERAL.amount, true);
  check(quantity.amount >= min_collateral, "not enough collateral");
  
  if (dcr > 0) {
    
    // check if debt amount is above the limit (actual amount is calculated at maturity)
    const auto debt_amount = to_buck(quantity.amount) / dcr;
    issue_debt = asset(debt_amount, BUCK);
    check(issue_debt >= MIN_DEBT, "not enough collateral to receive minimum debt");
  }
  
  const auto maturity = sub_funds(account, quantity);
  
  // open account if doesn't exist and update ram payer
  add_balance(account, ZERO_BUCK, account);
  add_funds(account, ZERO_REX, account, FAR_PAST);
  
  const auto id = _cdp.available_primary_key();
  _cdp.emplace(account, [&](auto& r) {
    r.id = id;
    r.account = account;
    r.icr = icr;
    r.collateral = quantity;
    r.debt = issue_debt;
    r.modified_round = now;
    r.maturity = maturity;
  });
  
  if (issue_debt.amount == 0) {
    set_excess_collateral(_cdp.require_find(id));
  }
  else {
    update_supply(issue_debt);
    add_balance(account, issue_debt, account);
  }
  
  run(5);
}