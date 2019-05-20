// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

void buck::process_maturities(const fund_i::const_iterator& fund_itr) {
  const time_point_sec now = current_time_point_sec();
  _fund.modify(fund_itr, same_payer, [&](auto& r) {
    while (!r.rex_maturities.empty() && r.rex_maturities.front().first <= now) {
      r.matured_rex += r.rex_maturities.front().second;
      r.rex_maturities.pop_front();
    }
  });
}


time_point_sec buck::get_maturity() const {
  const uint32_t num_of_maturity_buckets = 5;
  static const uint32_t now = current_time_point_sec().utc_seconds;
  static const uint32_t r   = now % seconds_per_day;
  static const time_point_sec rms{ now - r + num_of_maturity_buckets * seconds_per_day };
  return rms;
}

/// rex -> eos -> buck
int64_t buck::to_buck(int64_t quantity) const {
  static const int64_t EU = get_eos_usd_price();
  return convert(uint128_t(quantity) * EU, false);
}

/// buck -> eos -> rex
int64_t buck::to_rex(int64_t quantity, int64_t tax) const {
  static const int64_t EU = get_eos_usd_price();
  return convert(quantity, true) / (EU * (100 + tax) / 100);
}

/// eos -> rex (true)
/// rex -> eos (false)
int64_t buck::convert(uint128_t quantity, bool to_rex) const {
  rex_pool_i _pool(REX_ACCOUNT, REX_ACCOUNT.value);
  const auto pool_itr = _pool.begin();
  if (pool_itr == _pool.end()) return quantity; // test net case (1 rex = 1 eos)
  
  static const int64_t R0 = pool_itr->total_rex.amount;
  static const int64_t S0 = pool_itr->total_lendable.amount;
  
  if (to_rex) return quantity * R0 / S0;
  else return quantity * S0 / R0;
}

asset buck::get_rex_balance() const {
  rex_balance_i _balance(REX_ACCOUNT, REX_ACCOUNT.value);
  const auto balance_itr = _balance.find(_self.value);
  if (balance_itr == _balance.end()) return ZERO_REX;
  return balance_itr->rex_balance;
}

asset buck::get_eos_rex_balance() const {
  rex_fund_i _balance(REX_ACCOUNT, REX_ACCOUNT.value);
  const auto balance_itr = _balance.find(_self.value);
  if (balance_itr == _balance.end()) return ZERO_EOS;
  return balance_itr->balance;
}

void buck::processrex() {
  /// The code of this function has been temporarily removed in order to protect intellectual property. 
  /// Once the protocol will be used by several hundred users, the code wil be uploaded.
}

void buck::buy_rex(const name& account, const asset& quantity) {
  /// The code of this function has been temporarily removed in order to protect intellectual property. 
  /// Once the protocol will be used by several hundred users, the code wil be uploaded.
}

void buck::sell_rex(const name& account, const asset& quantity) {
  /// The code of this function has been temporarily removed in order to protect intellectual property. 
  /// Once the protocol will be used by several hundred users, the code wil be uploaded.
}