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
		transfer(eosio_token, master, user1, "1000000.0000 EOS", "")

	def run(self, result=None):
		super().run(result)

	# tests 
	
	def test(self):

		SCENARIO("Testing requests collision")

		###################################
		COMMENT("Setup")

		maketime(buck, 0)
		update(buck)

		transfer(eosio_token, user1, buck, "101.0000 EOS", "deposit")

		maketime(buck, 3_000_000)
		open(buck, user1, 200, 0, "100000.0000 REX")

		self.assertEqual(1000, fundbalance(buck, user1))
		self.assertEqual(100000, balance(buck, user1))

		###################################
		COMMENT("Make requests")

		close(buck, user1, 0)
		self.assertEqual(1000, fundbalance(buck, user1))
		self.assertEqual(0, balance(buck, user1))

		reparam(buck, user1, 0, "0.0000 BUCK", "500.0000 REX")
		self.assertEqual(500, fundbalance(buck, user1))
		self.assertEqual(100000, balance(buck, user1))

		close(buck, user1, 0)
		self.assertEqual(1000, fundbalance(buck, user1))
		self.assertEqual(0, balance(buck, user1))

		reparam(buck, user1, 0, "-500.0000 BUCK", "000.0000 REX")
		self.assertEqual(1000, fundbalance(buck, user1))
		self.assertEqual(99500, balance(buck, user1))

		close(buck, user1, 0)
		self.assertEqual(1000, fundbalance(buck, user1))
		self.assertEqual(0, balance(buck, user1))


		





# main

if __name__ == "__main__":
	unittest.main()