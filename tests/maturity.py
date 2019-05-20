# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import unittest, random, string
from eosfactory.eosf import *
import eosfactory.core.setup as setup 
from methods import *

verbosity([Verbosity.INFO, Verbosity.OUT, Verbosity.TRACE, Verbosity.DEBUG])

CONTRACT_WORKSPACE = "eos-buck"

# methods

class Test(unittest.TestCase):

	# setup
	setup.is_raise_error = True
	# setup.is_print_command_line = True

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

		# Distribute tokens

		create_issue(eosio_token, master, "EOS")

		# Users

		create_account("user1", master, "user1")
		transfer(eosio_token, master, user1, "10.0000 EOS", "")
		transfer(eosio_token, master, buck, "10.0000 EOS", "")
		
		deploy(Contract(buck, "eos-bucks/src"))
		deploy(Contract(rex, "eos-bucks/tests/rexmock"))

	def run(self, result=None):
		super().run(result)

	# tests

	def test(self):
		SCENARIO("Testing maturity")
		D = 24 * 60 * 60 + 1


		####################################
		COMMENT("Setup")

		time = 0 # day 1
		maketime(buck, time)
		update(buck)


		####################################
		COMMENT("Deposit maturity")


		# receive 1000 REX
		transfer(eosio_token, user1, buck, "1.0000 EOS", "deposit")

		maturities = table(buck, "fund", row=1, element="rex_maturities")
		self.assertEqual("1970-01-06T00:00:00", maturities[0]["first"])
		self.assertEqual(1000_0000, maturities[0]["second"])

		time += D # day 2
		maketime(buck, time)

		# receive 999 REX
		transfer(eosio_token, user1, buck, "1.0000 EOS", "deposit")

		maturities = table(buck, "fund", row=1, element="rex_maturities")
		self.assertEqual("1970-01-06T00:00:00", maturities[0]["first"])
		self.assertEqual(1000_0000, maturities[0]["second"])
		self.assertEqual("1970-01-07T00:00:00", maturities[1]["first"])
		self.assertEqual(999_0000, maturities[1]["second"])

		# receive 998 REX
		transfer(eosio_token, user1, buck, "1.0000 EOS", "deposit")

		maturities = table(buck, "fund", row=1, element="rex_maturities")
		self.assertEqual("1970-01-07T00:00:00", maturities[1]["first"])
		self.assertEqual(1997_0000, maturities[1]["second"])

		time += D * 4 # day 6
		maketime(buck, time)

		# receive 997 REX
		transfer(eosio_token, user1, buck, "2.0000 EOS", "deposit")

		# first bucket removed
		self.assertEqual(1000_0000, table(buck, "fund", row=1, element="matured_rex"))

		maturities = table(buck, "fund", row=1, element="rex_maturities")
		self.assertEqual("1970-01-07T00:00:00", maturities[0]["first"])
		self.assertEqual(1997_0000, maturities[0]["second"])
		self.assertEqual("1970-01-11T00:00:00", maturities[1]["first"])
		self.assertEqual(1994_0000, maturities[1]["second"])


		####################################
		COMMENT("Withdraw maturity")


		assertRaises(self, lambda: withdraw(buck, user1, "1001.0000 REX"))

		time += D * 1 # day 7
		maketime(buck, time)

		assertRaises(self, lambda: withdraw(buck, user1, "2998.0000 REX"))

		withdraw(buck, user1, "1997.0000 REX")

		self.assertEqual(1000_0000, table(buck, "fund", row=1, element="matured_rex"))


		####################################
		COMMENT("Check CDP maturity")

		open(buck, user1, 200, 0, "997.0000 REX")
		open(buck, user1, 200, 0, "1000.0000 REX")

		cdp = table(buck, "cdp", row=None)
		self.assertEqual(997, amount(cdp[0]["collateral"]))
		self.assertEqual("1970-01-01T00:00:00", cdp[0]["maturity"])
		self.assertEqual(1000, amount(cdp[1]["collateral"]))
		self.assertEqual("1970-01-11T00:00:00", cdp[1]["maturity"])
		
		####################################
		COMMENT("Reparam maturity")

		# receive 996 REX
		transfer(eosio_token, user1, buck, "1.0000 EOS", "deposit")

		time += D * 1 # day 8
		maketime(buck, time)

		table(buck, "cdp")

		reparam(buck, user1, 0, "0.0000 BUCK", "3.0000 REX")

		reparam(buck, user1, 1, "0.0000 BUCK", "1000.0000 REX")

		time += D * 3 # day 11
		maketime(buck, time)

		table(buck, "testtime")

		reparam(buck, user1, 1, "0.0000 BUCK", "1000.0000 REX")

		self.assertEqual("1970-01-11T00:00:00", table(buck, "reparamreq", row=0, element="maturity"))
		self.assertEqual("1970-01-12T00:00:00", table(buck, "reparamreq", row=1, element="maturity"))

		time += 100 # day 11
		maketime(buck, time)
		update(buck)

		cdp = table(buck, "cdp", row=None)
		self.assertEqual("1970-01-01T00:00:00", cdp[0]["maturity"])
		self.assertEqual("1970-01-12T00:00:00", cdp[1]["maturity"])
		

		####################################
		COMMENT("Maturity returns with cdp close/reparam")


		time += D * 100 # day 1 for new cycle (1970-04-26T00:00:00)
		maketime(buck, time)
		update(buck)
		
		withdraw(buck, user1, "989.0000 REX")

		# new funds, receive 1986 REX
		transfer(eosio_token, user1, buck, "2.0000 EOS", "deposit")

		# use all for cdp
		open(buck, user1, 200, 0, "1986.0000 REX")

		# check funds
		self.assertEqual(0, fundbalance(buck, user1))
		self.assertEqual(0, len(table(buck, "fund", row=1, element="rex_maturities")))

		# close request
		close(buck, user1, 2)

		time += 600
		maketime(buck, time)
		update(buck)
		
		# check funds
		self.assertEqual(1986, fundbalance(buck, user1))
		self.assertEqual("1970-04-26T00:00:00", table(buck, "fund", row=1, element="rex_maturities")[0]["first"])
		self.assertEqual(1986_0000, table(buck, "fund", row=1, element="rex_maturities")[0]["second"])





# main

if __name__ == "__main__":
	unittest.main()
