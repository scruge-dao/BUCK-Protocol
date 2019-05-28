// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

void buck::run(uint8_t max) {

  check(_stat.begin() != _stat.end(), "contract is not yet initiated");
  
  const uint8_t value = std::max(uint8_t(1), std::min(max, uint8_t(70)));
  if (get_liquidation_status() == LiquidationStatus::processing_liquidation) {
    run_liquidation(value);
  }
  else {
    run_requests(value);
  }
}

void buck::run_requests(uint8_t max) {
  
  // check if request processing have been frozen
  if (!check_operation_status(0)) return;
  
  const time_point oracle_timestamp = _stat.begin()->oracle_timestamp;
  const uint32_t now = time_point_sec(oracle_timestamp).utc_seconds;
  uint8_t status = get_processing_status();
  
  // loop until any requests exist and not over limit
  for (int i = 0; i < max; i++) {
    
    if (status == ProcessingStatus::processing_cdp_requests) {
          
      auto reparam_itr = _reparamreq.begin();
      auto close_itr = _closereq.begin();
      
      bool did_work = false;

      // close request
      if (close_itr != _closereq.end() && close_itr->timestamp < oracle_timestamp) {
        
        // find cdp
        const auto cdp_itr = _cdp.find(close_itr->cdp_id);
        if (cdp_itr == _cdp.end()) {
          cancel_previous_requests(reparam_itr->cdp_id);
          close_itr = _closereq.begin();
          did_work = true;
          continue;
        }
        
        remove_excess_collateral(cdp_itr);
        update_supply(-cdp_itr->debt);
        add_funds(cdp_itr->account, cdp_itr->collateral, same_payer, cdp_itr->maturity);
        _cdp.erase(cdp_itr);
        close_itr = _closereq.erase(close_itr);
        did_work = true;
      }
      
      // reparam request
      if (reparam_itr != _reparamreq.end() && reparam_itr->timestamp < oracle_timestamp) {
        
        // find cdp
        const auto cdp_itr = _cdp.find(reparam_itr->cdp_id);
        if (cdp_itr == _cdp.end()) {
          cancel_previous_requests(reparam_itr->cdp_id);
          reparam_itr = _reparamreq.begin();
          did_work = true;
          continue;
        }
        
        accrue_interest(cdp_itr, false);
        remove_excess_collateral(cdp_itr);
        
        asset change_debt = ZERO_BUCK;
        asset change_collateral = ZERO_REX;
        
         // removing debt
        if (reparam_itr->change_debt.amount < 0) {
          change_debt = reparam_itr->change_debt;
          update_supply(change_debt);
        }
        
        // adding collateral
        if (reparam_itr->change_collateral.amount > 0) { 
          change_collateral = reparam_itr->change_collateral;
        }
        
        // removing collateral
        if (reparam_itr->change_collateral.amount < 0) { 
          const auto new_debt = change_debt + cdp_itr->debt;

          if (new_debt.amount == 0) {
            change_collateral = reparam_itr->change_collateral;
          }
          else {
            
            int32_t dcr = to_buck(cdp_itr->collateral.amount) / new_debt.amount;
            if (dcr >= CR) {
              const int64_t m = cdp_itr->collateral.amount - to_rex(CR * new_debt.amount, 0);
              const int64_t change_amount = std::max(-m, reparam_itr->change_collateral.amount); // min out of negatives
              change_collateral = asset(change_amount, REX);
            }
          }

          // if not 0, add funds
          if (change_collateral.amount < 0) {
            add_funds(cdp_itr->account, -change_collateral, same_payer, cdp_itr->maturity);
          }
        }
        
        // adding debt
        if (reparam_itr->change_debt.amount > 0) {
          const auto new_collateral_amount = change_collateral.amount + cdp_itr->collateral.amount;
        
          int64_t max_debt = 0;
          
          if (cdp_itr->debt.amount > 0) {
            
            const int32_t dcr = to_buck(new_collateral_amount) / cdp_itr->debt.amount;
            
            if (dcr >= CR) {
              max_debt = (to_buck(new_collateral_amount * 100) / (CR * cdp_itr->debt.amount) - 100) * cdp_itr->debt.amount / 100;
            }
          }
          else {
            max_debt = to_buck(new_collateral_amount) / CR;
          }
          
          const int64_t change_amount = std::min(max_debt, reparam_itr->change_debt.amount);
          change_debt = asset(change_amount, BUCK);
          
          if (change_debt.amount > 0) {
            update_supply(change_debt);
            add_balance(cdp_itr->account, change_debt, same_payer);
          }
        }
        
        _cdp.modify(cdp_itr, same_payer, [&](auto& r) {
          r.collateral += change_collateral;
          r.debt += change_debt;
          
          if (reparam_itr->maturity >= oracle_timestamp) {
            r.maturity = reparam_itr->maturity;
          }
        });
        
        // sanity check
        check(cdp_itr->debt.amount >= 0, "programmer error, debt can't go below 0");
        check(cdp_itr->collateral.amount >= 0, "programmer error, collateral can't go below 0");
      
        set_excess_collateral(cdp_itr);
        
        reparam_itr = _reparamreq.erase(reparam_itr);
        did_work = true;
      }
      
      if (!did_work) {
        
        set_processing_status(ProcessingStatus::processing_redemption_requests);
        status = ProcessingStatus::processing_redemption_requests;
        continue;
      }
    }
    else if (status == ProcessingStatus::processing_redemption_requests) {
      
      auto debtor_index = _cdp.get_index<"debtor"_n>();
      auto debtor_itr = debtor_index.begin();
      auto redeem_itr = _redeemreq.begin();
      
      // redeem request
      if (redeem_itr != _redeemreq.end() && redeem_itr->timestamp < oracle_timestamp) {
        
        auto redeem_quantity = redeem_itr->quantity;
        asset rex_return = ZERO_REX;
        asset collateral_return = ZERO_REX;
        debtor_itr = debtor_index.begin();
        
        // loop protection
        uint8_t debtors_failed = 0;
        
        // loop through available debtors until all amount is redeemed or our of debtors
        while (redeem_quantity.amount > 0 && debtor_itr != debtor_index.end() && debtors_failed < 30) {
          
          if (debtor_itr->collateral.amount == 0 || debtor_itr->debt.amount == 0) { // reached end of the table
            break;
          }
          
          accrue_interest(_cdp.require_find(debtor_itr->id), false);
          
          if (debtor_itr->debt < MIN_DEBT) { // don't go below min debt
            debtors_failed++;
            debtor_itr++;
            continue;
          }
          
          const int32_t dcr = to_buck(debtor_itr->collateral.amount) / debtor_itr->debt.amount;
          
          // all further debtors have even worse dcr
          if (dcr < 100 - RF) { 
            debtors_failed++;
            debtor_itr++;
            continue;
          }
          
          const int64_t using_debt_amount = std::min(redeem_quantity.amount, debtor_itr->debt.amount);
          const int64_t using_collateral_amount = to_rex(using_debt_amount * 100, RF);
        
          const asset using_debt = asset(using_debt_amount, BUCK);
          const asset using_collateral = asset(using_collateral_amount, REX);
          
          redeem_quantity -= using_debt;
          collateral_return += using_collateral;
          
          if (debtor_itr->debt == using_debt) {
            const asset left_over_collateral = debtor_itr->collateral - using_collateral;
            
            if (left_over_collateral.amount > 0) {
              add_funds(debtor_itr->account, left_over_collateral, same_payer, debtor_itr->maturity);
            }
            
            debtor_index.erase(debtor_itr); 
          }
          else {
            debtor_index.modify(debtor_itr, same_payer, [&](auto& r) {
              r.debt -= using_debt;
              r.collateral -= using_collateral;
            });
            
            // sanity check
            check(debtor_itr->debt.amount >= 0, "programmer error, debt can't go below 0");
            check(debtor_itr->collateral.amount >= 0, "programmer error, collateral can't go below 0");
          }
          
          // next best debtor will be the first in table (after this one changed)
          debtor_itr = debtor_index.begin();
        }
        
        const auto burned_debt = redeem_itr->quantity - redeem_quantity;
        
        // done with this redemption request
        if (burned_debt.amount > 0) {
          
          if (redeem_quantity.amount > 0) {
            
            // return unredeemed amount
            add_balance(redeem_itr->account, redeem_quantity, same_payer);
          }
          
          // complete and remove redemption request only if anything was redeemed in the process
          update_supply(-burned_debt);
          add_funds(redeem_itr->account, collateral_return, same_payer, FAR_PAST);
          redeem_itr = _redeemreq.erase(redeem_itr);
        }
        
        // in extreme situations, only do 1 request per run
        if (debtors_failed > 1) break;
      }
      else {
        // no more redemption requests
        set_processing_status(ProcessingStatus::processing_complete);
        break;
      }
    }
    else { break; }
  }
  
  const uint8_t m = std::min(uint8_t(50), max);
  collect_taxes(m);
  run_exchange(m);
}

void buck::run_liquidation(uint8_t max) {

  // check if liquidation processing have been frozen
  if (!check_operation_status(1)) return;
  
  uint64_t processed = 0;
  const auto now = get_current_time_point();
  
  auto debtor_index = _cdp.get_index<"debtor"_n>();
  auto liquidator_index = _cdp.get_index<"liquidator"_n>();
  auto liquidator_itr = liquidator_index.begin();
  
  // no cdp exist, quit
  if (liquidator_itr == liquidator_index.end()) return; 
  
  // loop through liquidators
  while (max > processed) {
    const auto liquidator_itr = liquidator_index.begin();
    const auto debtor_itr = debtor_index.begin();
    
    accrue_interest(_cdp.require_find(debtor_itr->id), false);
    
    if (debtor_itr->debt.amount == 0) {
      set_liquidation_status(LiquidationStatus::liquidation_complete);
      run_requests(max - processed);
      return;
    }
    
    const int64_t debt_amount = debtor_itr->debt.amount;
    const int64_t collateral_amount = debtor_itr->collateral.amount;
    const int64_t debtor_dcr = to_buck(collateral_amount) / debt_amount;
    
    if (debtor_dcr >= CR) {
      
      set_liquidation_status(LiquidationStatus::liquidation_complete);
      run_requests(max - processed);
      return;
    }
    
    // check icr
    if (liquidator_itr->icr == 0) {
      
      set_liquidation_status(LiquidationStatus::failed);
      run_requests(max - processed);
      return;
    }
    
    const auto liquidator_cdp_itr = _cdp.require_find(liquidator_itr->id);
    
    processed++;
    remove_excess_collateral(liquidator_cdp_itr);
    accrue_interest(liquidator_cdp_itr, false);
    
    const int64_t liquidator_collateral = liquidator_itr->collateral.amount;
    const int64_t liquidator_debt = liquidator_itr->debt.amount;
    const int64_t liquidator_icr = liquidator_itr->icr;
    
    int64_t liquidator_dcr = 9999999;
    if (liquidator_debt > 0) {
      liquidator_dcr = to_buck(liquidator_collateral) / liquidator_debt;
    }
    
    if (liquidator_dcr < CR || liquidator_debt > 0 && liquidator_dcr <= liquidator_icr) {
      set_liquidation_status(LiquidationStatus::failed);
      run_requests(max - processed);
      return;
    }
    
    int64_t liquidation_fee = LF;
    if (debtor_dcr >= 100 + LF) { liquidation_fee = LF; }
    else if (debtor_dcr < 75) { liquidation_fee = -25; }
    else { liquidation_fee = debtor_dcr - 100; }
    
    const int64_t bad_debt = (CR * debt_amount - to_buck(collateral_amount)) / (CR - 100 - liquidation_fee);
    
    const int64_t bailable = (to_buck(liquidator_collateral) - (liquidator_debt * liquidator_icr)) 
        * (100 - liquidation_fee) / (liquidator_icr * (100 - liquidation_fee) - 10'000);
    
    const int64_t used_debt_amount = std::min(std::min(bad_debt, bailable), debt_amount);
    const int64_t value2 = to_rex(used_debt_amount * 100, 0) * (100 + liquidation_fee) / 100;
    
    const int64_t used_collateral_amount = std::min(collateral_amount, value2);
    
    const asset used_debt = asset(used_debt_amount, BUCK);
    const asset used_collateral = asset(used_collateral_amount, REX);
    
    // check if using debt is 0
    if (used_debt.amount == 0) {
      
      set_liquidation_status(LiquidationStatus::liquidation_complete);
      run_requests(max - processed);
      return;
    }
    
    liquidator_index.modify(liquidator_itr, same_payer, [&](auto& r) {
      r.collateral += used_collateral;
      r.debt += used_debt;
      
      // if debtor maturity more than liquidator maturity and more than current time
      if (debtor_itr->maturity > now && debtor_itr->maturity > liquidator_itr->maturity) {
        r.maturity = debtor_itr->maturity; // pass maturity
      }
    });
    
    set_excess_collateral(liquidator_cdp_itr);
    const bool removed = debtor_itr->debt == used_debt;
    if (removed) {
      debtor_index.erase(debtor_itr);
    }
    else {
      debtor_index.modify(debtor_itr, same_payer, [&](auto& r) {
        r.collateral -= used_collateral;
        r.debt -= used_debt;
      });
      
      // sanity check
      check(debtor_itr->debt.amount >= 0, "programmer error, debt can't go below 0");
      check(debtor_itr->collateral.amount >= 0, "programmer error, collateral can't go below 0");
    }
    
    // sanity check
    check(liquidator_itr->debt.amount >= 0, "programmer error, debt can't go below 0");
    check(liquidator_itr->collateral.amount >= 0, "programmer error, collateral can't go below 0");
    
    processed++;
  }
}