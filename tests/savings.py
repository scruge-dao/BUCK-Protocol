# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import unittest
from eosfactory.eosf import *
import eosfactory.core.setup as setup 
from methods import *
from time import sleep
import string

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
		create_account("user2", master, "user2")
		create_account("user3", master, "user3")
		transfer(eosio_token, master, user1, "1000000000.0000 EOS", "")
		transfer(eosio_token, master, user2, "1000000000.0000 EOS", "")

	def run(self, result=None):
		super().run(result)

	# tests 
	
	def test(self):
		SCENARIO("Testing savings")

		time = 0
		maketime(buck, time)
		update(buck, 100)

		transfer(eosio_token, user1, buck, "1000000000.0000 EOS", "deposit")
		transfer(eosio_token, user2, buck, "1000000000.0000 EOS", "deposit")

		# mature rex
		time += 3_000_000
		maketime(buck, time)

		open(buck, user1, 1000, 0, "10000.0000 REX") # 1000.0000 BUCK
		open(buck, user2, 1000, 0, "10000.0000 REX") # 1000.0000 BUCK

		##############################
		COMMENT("Initialize")

		maketime(buck, time)
		update(buck, 100)

		##############################
		COMMENT("Save")

		save(buck, user1, "1.0000 BUCK")
		balance(buck, user1)

		# save
		time += 3_000_000
		maketime(buck, time)
		update(buck, 100)

		save(buck, user2, "1.0000 BUCK")
		balance(buck, user2)

		transfer(buck, user1, user3, "999.0000 BUCK", "")
		transfer(buck, user2, user3, "999.0000 BUCK", "")

		# assert money went away
		self.assertEqual(0, balance(buck, user1))
		self.assertEqual(0, balance(buck, user2))

		# save more
		time += 3_000_000
		maketime(buck, time)
		update(buck, 100)

		tax1 = table(buck, "taxation")

		balance(buck, user1)
		balance(buck, user2)

		##############################
		COMMENT("Take")

		unsave(buck, user1, 10000)
		unsave(buck, user2, 1408)

		##############################
		COMMENT("Match")

		tax2 = table(buck, "taxation")

		self.assertEqual(0, amount(tax2["savings_pool"]), "savings pool is not empty")

		balance1 = balance(buck, user1)
		balance2 = balance(buck, user2)
		difference = balance1 + balance2 - amount(tax1["savings_pool"])
		self.assertEqual(0, difference, "savings pool doesn't match balances")



		


# main

if __name__ == "__main__":
	unittest.main()