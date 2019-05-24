// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

/// defines if contract will print logs and enable debug features
#define DEBUG false
/// defines if contract uses test rex environment
#define REX_TESTING false
/// defines if testing of time points is enabled
#define TEST_TIME false

static const uint32_t seconds_per_day     = 86'400;
static const uint32_t YEAR                = 31'557'600;
static const uint32_t ACCRUAL_PERIOD      = 1'314'900;

static const symbol& EOS   = symbol("EOS", 4);
static const symbol& BUCK  = symbol("BUCK", 4);
static const symbol& REX   = symbol("REX", 4);

static const asset& ZERO_BUCK  = asset(0, BUCK);
static const asset& ZERO_REX   = asset(0, REX);
static const asset& ZERO_EOS   = asset(0, EOS);

static const time_point_sec FAR_PAST = time_point_sec(0);

/// maximum ratio for ICR (%)
const uint64_t MAX_ICR = 1000;   

/// max % of price change available to oracle
static const uint8_t ORACLE_MAX_PERCENT = 8;

/// minimam collateral to become an insurer (~15 EOS)
static const asset MIN_INSURER_REX = asset(15'0000'0000, REX);

/// minimal collateral is 5 EOS
static const asset& MIN_COLLATERAL = asset(5'0000, EOS);

/// minimal amount to redeem
static const asset& MIN_REDEMPTION = asset(10'0000, BUCK);

/// minimal cdp debt is 50 BUCK
static const asset& MIN_DEBT       = asset(10'0000, BUCK);

static const name& EOSIO_TOKEN = "eosio.token"_n;
static const name& EOSIO       = "eosio"_n;
static const name& SCRUGE      = "equityscruge"_n;

#if REX_TESTING
/// account on jungle/local test net
static const name& REX_ACCOUNT  = "rexrexrexrex"_n;
#else
static const name& REX_ACCOUNT  = EOSIO;
#endif

// constants in %

const uint64_t CR = 150; /// minimal collateral ratio
const uint64_t LF = 10;  /// liquidation fee
const uint64_t RF = 1;   /// redemption fee
const uint64_t SP = 20;  /// part of taxes for scruge
const uint64_t SR = 80;   /// savings ratio
const uint64_t IR = 20;   /// insurance ratio
const double AR = 0.095;   /// annual interest rate