// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

void buck::process_taxes() {
  if (!check_operation_status(6)) return;
  const auto& tax = *_tax.begin();
  
  // send part of collected insurance to Scruge
  const int64_t scruge_insurance_amount = tax.collected_excess.amount * SP / 100;
  const int64_t insurance_amount = tax.collected_excess.amount - scruge_insurance_amount;
  const auto scruge_insurance = asset(scruge_insurance_amount, REX);
  if (scruge_insurance_amount > 0) {
    add_funds(SCRUGE, scruge_insurance, same_payer, FAR_PAST);
  }
  
  // send part of collected savings to Scruge
  const int64_t scruge_savings_amount = tax.collected_savings.amount * SP / 100;
  const int64_t savings_amount = tax.collected_savings.amount - scruge_savings_amount;
  const auto scruge_savings = asset(scruge_savings_amount, BUCK);
  if (scruge_savings_amount > 0) {
    add_balance(SCRUGE, scruge_savings, _self);
  }

  const auto oracle_time = _stat.begin()->oracle_timestamp;
  static const uint32_t last = time_point_sec(oracle_time).utc_seconds;
  static const uint32_t now = time_point_sec(get_current_time_point()).utc_seconds;
  static const uint32_t delta_t = now - last;
  
  _tax.modify(tax, same_payer, [&](auto& r) {
    
    r.insurance_pool += asset(insurance_amount, REX);
    r.savings_pool += asset(savings_amount, BUCK);
    
    r.aggregated_excess += r.total_excess * delta_t;
    r.collected_excess = ZERO_REX;
    
    r.collected_savings = ZERO_BUCK;
  });
  
  // sanity check
  check(tax.insurance_pool.amount >= 0, "programmer error, pools can't go below 0");
  check(tax.savings_pool.amount >= 0, "programmer error, pools can't go below 0");
}

void buck::collect_taxes(uint32_t max) {
  auto accrual_index = _cdp.get_index<"accrued"_n>();
  auto accrual_itr = accrual_index.begin();
  
  const time_point oracle_timestamp = _stat.begin()->oracle_timestamp;
  const uint32_t now = time_point_sec(oracle_timestamp).utc_seconds;
  
  int processed = 0;
  while (max > processed && accrual_itr != accrual_index.end()
          && now - accrual_itr->modified_round > ACCRUAL_PERIOD) {
  
    accrue_interest(_cdp.require_find(accrual_itr->id), false);
    accrual_itr = accrual_index.begin(); // take first element after index updated
    processed++;
  }
}

// collect interest to debtors
void buck::accrue_interest(const cdp_i::const_iterator& cdp_itr, bool accrue_min) {
  if (cdp_itr->debt.amount == 0) return;
  
  const auto oracle_time = _stat.begin()->oracle_timestamp;
  static const uint32_t now = time_point_sec(oracle_time).utc_seconds;
  const uint32_t last = cdp_itr->modified_round;
  
  if (now == last) return;
  const auto& tax = *_tax.begin();
  
  static const uint128_t DM = 1000000000000;
  const uint128_t v = (exp(AR * double(now - last) / double(YEAR)) - 1) * DM;
  const int64_t accrued_amount = cdp_itr->debt.amount * v / DM;
  
  const int64_t min = accrue_min ? 1 : 0;
  const int64_t accrued_debt_amount = std::max(min, int64_t(accrued_amount * SR / 100));
  const int64_t accrued_collateral_amount = std::max(min, to_rex(accrued_amount * IR, 0));
  
  const asset accrued_debt = asset(accrued_debt_amount, BUCK);
  const asset accrued_collateral = asset(accrued_collateral_amount, REX);

  _cdp.modify(cdp_itr, same_payer, [&](auto& r) {
    r.collateral -= accrued_collateral;
    r.debt += accrued_debt;
    r.modified_round = now;
  });
  
  _tax.modify(tax, same_payer, [&](auto& r) {
    r.collected_savings += accrued_debt;
    r.collected_excess += accrued_collateral;
  });

  update_supply(accrued_debt);
}

void buck::set_excess_collateral(const cdp_i::const_iterator& cdp_itr) {
  if (cdp_itr->debt.amount > 0 || cdp_itr->icr == 0) return;
  
  const auto& tax = *_tax.begin();
  const int64_t excess = cdp_itr->collateral.amount * 100 / cdp_itr->icr;
  const auto oracle_time = _stat.begin()->oracle_timestamp;
  static const uint32_t now = time_point_sec(oracle_time).utc_seconds;
  
  _cdp.modify(cdp_itr, same_payer, [&](auto& r) {
    r.modified_round = now;
  });
  
  _tax.modify(tax, same_payer, [&](auto& r) {
    r.total_excess += excess;
  });
}

void buck::remove_excess_collateral(const cdp_i::const_iterator& cdp_itr) {
  if (cdp_itr->icr == 0 || cdp_itr->debt.amount > 0) return;
  const auto& tax = *_tax.begin();
  
  const auto oracle_time = _stat.begin()->oracle_timestamp;
  static const uint32_t now = time_point_sec(oracle_time).utc_seconds;
  const uint32_t delta_t = now - cdp_itr->modified_round;
  
  const uint64_t excess = cdp_itr->collateral.amount * 100 / cdp_itr->icr;
  const uint128_t agec = uint128_t(excess) * delta_t;
  
  int64_t dividends_amount = 0;
  if (tax.aggregated_excess > 0) {
    dividends_amount = agec * tax.insurance_pool.amount / tax.aggregated_excess;
  }
  
  _tax.modify(tax, same_payer, [&](auto& r) {
    r.total_excess -= excess;
    r.aggregated_excess -= agec;
    r.insurance_pool -= asset(dividends_amount, REX);
  });
  
  _cdp.modify(cdp_itr, same_payer, [&](auto& r) {
    r.collateral += asset(dividends_amount, REX);
    r.modified_round = now;
  });
}

void buck::save(const name& account, const asset& quantity) {
  require_auth(account);
  const auto& tax = *_tax.begin();
  check(check_operation_status(7), "savings operations have been temporarily frozen");
  
  check(quantity.is_valid(), "invalid quantity");
  check(quantity.amount > 0, "can not use negative value");
  check(quantity.symbol == BUCK, "can not use asset with different symbol");
  check(quantity.amount >= 1'0000, "not enough value to put in savings");
  
  uint64_t received_amount = quantity.amount;
  if (tax.savings_supply > 0) {
    received_amount = (uint128_t) quantity.amount * tax.savings_supply / tax.savings_pool.amount;
  }
  
  check(received_amount > 0, "not enough quantity to receive minimum amount of savings");
  
  // create funds if doesn't exist
  add_funds(account, ZERO_REX, account, FAR_PAST);
  const auto fund_itr = _fund.require_find(account.value);
  
  _fund.modify(fund_itr, account, [&](auto& r) {
    r.savings_balance += received_amount;
  });
  
  _tax.modify(tax, same_payer, [&](auto& r) {
    r.savings_supply += received_amount;
    r.savings_pool += quantity;
  });
  
  sub_balance(account, quantity);
  run(3);
}

void buck::unsave(const name& account, const uint64_t quantity) {
  require_auth(account);
  const auto& tax = *_tax.begin();
  check(check_operation_status(7), "savings operations have been temporarily frozen");
  check(quantity > 0, "can not use negative value");
  
  accounts_i _accounts(_self, account.value);
  const auto account_itr = _accounts.find(BUCK.code().raw());
  const auto fund_itr = _fund.require_find(account.value, "fund object doesn't exist");
  check(fund_itr->savings_balance >= quantity, "overdrawn savings balance");
  
  const int64_t received_bucks_amount = uint128_t(quantity) * tax.savings_pool.amount / tax.savings_supply;
  const asset received_bucks = asset(received_bucks_amount, BUCK);
  
  _fund.modify(fund_itr, account, [&](auto& r) {
    r.savings_balance -= quantity;
  });
  
  _tax.modify(tax, same_payer, [&](auto& r) {
    r.savings_supply -= quantity;
    r.savings_pool -= asset(received_bucks_amount, BUCK);
  });
  
  add_balance(account, received_bucks, same_payer);
  run(3);
}