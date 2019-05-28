// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

void buck::setoperation(uint8_t level) {
  require_auth(_self);
  _stat.modify(_stat.begin(), same_payer, [&](auto& r) {
    r.operation_status = level;
  });
}

bool buck::check_operation_status(uint8_t task_number) const {
  return !(_stat.begin()->operation_status & 1 << task_number);
}

void buck::forceupdate(uint32_t eos_price) {
  require_auth(_self);
  _update(eos_price, true);
}

void buck::update(uint32_t eos_price) {
  require_auth(permission_level(_self, "oracle"_n));
  
  if (_stat.begin() != _stat.end()) {
    check(check_operation_status(4), "oracle updates have been temporarily frozen");
  }
  _update(eos_price, false);
}

void buck::_update(uint32_t eos_price, bool force) {
  
  init();
  process_taxes();
  
  const auto& stats = *_stat.begin();
  const uint32_t previous_price = stats.oracle_eos_price;
  int32_t new_price = eos_price;
  
  // shave off price change if don't have a special permission
  if (!force && previous_price != 0) {
    const uint32_t difference = std::abs(int32_t(previous_price) - int32_t(new_price));
    const uint32_t percent = difference * 100 / previous_price;
    
    // handle situations when any price difference is too big
    if (percent > ORACLE_MAX_PERCENT) {
      new_price = previous_price + (previous_price > new_price ? -1 : 1);
    }
  }
  
  // protect from 0 price
  new_price = std::max(1, new_price);
  
  _stat.modify(stats, same_payer, [&](auto& r) {
    r.oracle_timestamp = get_current_time_point();
    r.oracle_eos_price = new_price;
  });
  
  set_processing_status(ProcessingStatus::processing_cdp_requests);
  
  if (eos_price < previous_price) {
    set_liquidation_status(LiquidationStatus::processing_liquidation);
  }
}

uint32_t buck::get_eos_usd_price() const {
  check(_stat.begin() != _stat.end(), "contract is not yet initiated");
  return _stat.begin()->oracle_eos_price;
}