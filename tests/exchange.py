# coding: utf8
# Copyright © Scruge 2019.
# This file is part of ScrugeX.
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
		create_account("user2", master, "user2")
		create_account("user3", master, "user3")
		create_account("user4", master, "user4")

		transfer(eosio_token, master, user1, "1000000.0000 EOS", "")
		transfer(eosio_token, master, user2, "1000000.0000 EOS", "")
		transfer(eosio_token, master, user3, "1000000.0000 EOS", "")

	def run(self, result=None):
		super().run(result)

	# tests 
	
	def test(self):
		SCENARIO("Testing exchange")

		###################################
		COMMENT("Setup")

		maketime(buck, 0)
		update(buck)

		transfer(eosio_token, user1, buck, "1000000.0000 EOS", "deposit")
		transfer(eosio_token, user2, buck, "1000.0000 EOS", "exchange")
		transfer(eosio_token, user3, buck, "1000.0000 EOS", "exchange")

		maketime(buck, 3_000_000)
		open(buck, user1, 200, 0, "100000.0000 REX")

		# send bucks to user4
		transfer(buck, user1, user4, "2000.0000 BUCK", "")

		###################################
		COMMENT("Exchange")

		maketime(buck, 3_000_001)
		exchange(buck, user2, "500.0000 EOS")
		exchange(buck, user1, "2000.0000 BUCK")

		maketime(buck, 3_000_002)
		exchange(buck, user2, "500.0000 EOS")
		exchange(buck, user4, "1000.0000 BUCK")

		maketime(buck, 3_000_003)
		exchange(buck, user3, "500.0000 EOS")
		exchange(buck, user1, "500.0000 BUCK")

		maketime(buck, 3_000_004)
		exchange(buck, user3, "500.0000 EOS")
		exchange(buck, user4, "1000.0000 BUCK") # 500 BUCK excess

		# get rid of the rest of the bucks
		transfer(buck, user1, master, balance(buck, user1, unwrap=False), "")

		# sellers
		self.assertEqual(0, fundexbalance(buck, user1))
		self.assertEqual(0, fundexbalance(buck, user4))

		# buyers
		self.assertEqual(0, balance(buck, user2))
		self.assertEqual(0, balance(buck, user3))


		# run exchange
		maketime(buck, 4_000_000)
		update(buck)

		#################################
		COMMENT("Match")

		# user1 sells 2.5K BUCK
		# user4 sells 1.5K BUCK
		# user2 buys 1K EOS worth
		# user3 buys 1K EOS worth

		ex = table(buck, "exchange")
		self.assertEqual(500, amount(ex["quantity"]))
		self.assertEqual("user4", ex["account"])


		# sellers
		self.assertEqual(1250, fundexbalance(buck, user1))
		self.assertEqual(750, fundexbalance(buck, user4))

		# buyers
		self.assertEqual(2000, balance(buck, user2))
		self.assertEqual(2000, balance(buck, user3))





# main

if __name__ == "__main__":
	unittest.main()