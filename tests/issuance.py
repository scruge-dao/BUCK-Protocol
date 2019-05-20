# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import unittest
from eosfactory.eosf import *
from methods import *
from time import sleep
import string

verbosity([Verbosity.INFO, Verbosity.OUT, Verbosity.TRACE, Verbosity.DEBUG])

CONTRACT_WORKSPACE = "eos-buck"

# methods

class Test(unittest.TestCase):

	# setup

	@classmethod
	def tearDownClass(cls):
		stop()

	@classmethod
	def setUpClass(cls):
		reset()
		
		create_master_account("master")
		create_account("eosio_token", master, "eosio.token")
		create_account("rex", master, "rexrexrexrex")
		
		key = CreateKey(is_verbose=False)
		create_account("buck", master, "buck", key)
		perm(buck, key)

		deploy(Contract(eosio_token, "eosio_token"))
		deploy(Contract(buck, "eos-bucks/src"))
		deploy(Contract(rex, "eos-bucks/tests/rexmock"))

		# Distribute tokens

		create_issue(eosio_token, master, "EOS")

		# Users

		create_account("user1", master, "user1")
		transfer(eosio_token, master, user1, "10000000.0000 EOS", "")

	def run(self, result=None):
		super().run(result)

	# tests

	def test(self):
		SCENARIO("Test open and close cdp")

		time = 0
		maketime(buck, time)
		update(buck)

		##############################
		COMMENT("Deposit")

		transfer(eosio_token, user1, buck, "20.0000 EOS", "deposit")

		# check rex
		self.assertEqual(0, amount(table(rex, "rexfund", element="balance")))
		self.assertEqual(20000, amount(table(rex, "rexbal", element="rex_balance")))

		##############################
		COMMENT("Open CDP")

		open(buck, user1, 165, 0, "10000.0000 REX")

		# issuance formula
		price = 200
		col = 100000000
		ccr = 165
		debt = price * col // ccr / 10000

		# check buck balance
		self.assertEqual(debt, balance(buck, user1))

		# check all cdp values
		cdp = table(buck, "cdp")
		self.assertEqual(10000, amount(cdp["collateral"]))
		self.assertEqual(debt, amount(cdp["debt"]))
		self.assertAlmostEqual(0, float(cdp["icr"]))
		self.assertEqual("user1", cdp["account"])
		self.assertEqual("1970-01-06T00:00:00", cdp["maturity"]) # in 5 days

		##############################
		COMMENT("Close CDP")

		# prepare to pay buck to close cdp #1 
		open(buck, user1, 165, 0, "10000.0000 REX")
		self.assertEqual(24242.4242, balance(buck, user1))

		self.assertEqual(0, fundbalance(buck, user1))

		time += 500_000
		maketime(buck, time)
		update(buck)

		close(buck, user1, 0)
		table(buck, "closereq")

		time += 10
		maketime(buck, time)
		update(buck)

		cdp = table(buck, "cdp")

		self.assertEqual(0, len(table(buck, "closereq")))

		self.assertLess(9999, fundbalance(buck, user1))
		self.assertGreater(10000, fundbalance(buck, user1))




# main

if __name__ == "__main__":
	unittest.main()