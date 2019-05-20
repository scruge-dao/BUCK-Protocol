# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import unittest
from eosfactory.eosf import *
from methods import *
import eosfactory.core.setup as setup 
from time import sleep
import string
import datetime
import test

verbosity([Verbosity.INFO, Verbosity.OUT, Verbosity.TRACE, Verbosity.DEBUG])

CONTRACT_WORKSPACE = "eos-buck"

# methods

class Test(unittest.TestCase):

	# setup
	setup.is_raise_error = True

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

		transfer(eosio_token, master, user1, "1000000000000.0000 EOS", "")

	def run(self, result=None):
		super().run(result)

	# tests

	### check rex values when selling rex

	def test(self):
		SCENARIO("Testing cdp reparametrization")

		time = 0
		maketime(buck, time)
		update(buck, 100)

		transfer(eosio_token, user1, buck, "102.0000 EOS", "deposit")

		# mature rex
		time += 3_000_000
		maketime(buck, time)
		update(buck, 100)

		open(buck, user1, 0, 200, "10000.0000 REX") # 1000.0000 BUCK
		open(buck, user1, 0, 200, "10000.0000 REX")
		open(buck, user1, 0, 200, "10000.0000 REX")
		open(buck, user1, 0, 200, "10000.0000 REX")
		open(buck, user1, 0, 200, "10000.0000 REX")
		open(buck, user1, 1000, 0, "10000.0000 REX")
		open(buck, user1, 1000, 0, "10000.0000 REX")
		open(buck, user1, 1000, 0, "10000.0000 REX")
		open(buck, user1, 1000, 0, "10000.0000 REX")
		open(buck, user1, 1000, 0, "10000.0000 REX")

		# remove excess buck
		transfer(buck, user1, master, "4950.0000 BUCK", "")

		self.assertEqual(2000, fundbalance(buck, user1))
		self.assertEqual(50, balance(buck, user1))

		##############################
		COMMENT("Reparam liquidator CDPs")

		# remove debt - error
		assertRaises(self, lambda: reparam(buck, user1, 0, "-50.0000 BUCK", "0.0000 REX"))

		# change acr
		assertRaises(self, lambda: changeacr(buck, user1, 0, 149))
		changeacr(buck, user1, 0, 150)

		# add debt
		reparam(buck, user1, 1, "50.0000 BUCK", "0.0000 REX")
		# remove collateral
		reparam(buck, user1, 2, "0.0000 BUCK", "-1000.0000 REX")
		# add collateral
		reparam(buck, user1, 3, "0.0000 BUCK", "1000.0000 REX")
		# both
		reparam(buck, user1, 4, "50.0000 BUCK", "-1000.0000 REX")

		##############################
		COMMENT("Reparam debtor CDPs")

		# remove debt
		reparam(buck, user1, 5, "-50.0000 BUCK", "0.0000 REX")
		# add debt
		reparam(buck, user1, 6, "50.0000 BUCK", "0.0000 REX")
		# remove collateral
		reparam(buck, user1, 7, "0.0000 BUCK", "-1000.0000 REX")
		# add collateral
		reparam(buck, user1, 8, "0.0000 BUCK", "1000.0000 REX")
		# both
		reparam(buck, user1, 9, "50.0000 BUCK", "-1000.0000 REX")

		##############################
		COMMENT("Oracle")

		self.assertEqual(0, fundbalance(buck, user1))
		self.assertEqual(0, balance(buck, user1))

		# mature rex
		time += 1
		maketime(buck, time)
		update(buck, 100)

		##############################
		COMMENT("Match")

		cdps = table(buck, "cdp", row=None)

		self.assertEqual(50, amount(cdps[1]["debt"]))
		self.assertEqual(10000, amount(cdps[1]["collateral"]))

		self.assertEqual(0, amount(cdps[2]["debt"]))
		self.assertEqual(9000, amount(cdps[2]["collateral"]))

		self.assertEqual(0, amount(cdps[3]["debt"]))
		self.assertEqual(11000, amount(cdps[3]["collateral"]))

		self.assertEqual(50, amount(cdps[4]["debt"]))
		self.assertEqual(9000, amount(cdps[4]["collateral"]))

		##############################

		self.assertEqual(150, cdps[0]["icr"])

		self.assertEqual(950, amount(cdps[5]["debt"]))
		self.assertEqual(10000, amount(cdps[5]["collateral"]))

		self.assertEqual(1050, amount(cdps[6]["debt"]))
		self.assertEqual(10000, amount(cdps[6]["collateral"]))

		self.assertEqual(1000, amount(cdps[7]["debt"]))
		self.assertEqual(9000, amount(cdps[7]["collateral"]))

		self.assertEqual(1000, amount(cdps[8]["debt"]))
		self.assertEqual(11000, amount(cdps[8]["collateral"]))

		self.assertEqual(1050, amount(cdps[9]["debt"]))
		self.assertEqual(9000, amount(cdps[9]["collateral"]))

		self.assertEqual(4000, fundbalance(buck, user1))
		self.assertEqual(200, balance(buck, user1))


		##############################
		COMMENT("Reparam debtor CDP to insurer")
		
		transfer(eosio_token, user1, buck, "10.0000 EOS", "deposit")
		
		# mature rex
		time += 500_000
		maketime(buck, time)
		update(buck, 100)

		open(buck, user1, 1000, 0, "10000.0000 REX")

		assertRaises(self, lambda: reparam(buck, user1, 10, "-1000.0001 BUCK", "0.0000 REX"))

		reparam(buck, user1, 10, "-1000.0000 BUCK", "0.0000 REX")

		# mature rex
		time += 100
		maketime(buck, time)
		update(buck, 100)

		table(buck, "cdp", limit=11)

# main

if __name__ == "__main__":
	unittest.main()