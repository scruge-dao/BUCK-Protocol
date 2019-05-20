# coding: utf8
# Copyright © Scruge 2019.
# This file is part of ScrugeX.
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
		transfer(eosio_token, master, user1, "2.0000 EOS", "")
		transfer(eosio_token, master, buck, "10.0000 EOS", "")
		
		deploy(Contract(buck, "eos-bucks/src"))
		deploy(Contract(rex, "eos-bucks/tests/rexmock"))

	def run(self, result=None):
		super().run(result)

	# tests

	def test(self):
		SCENARIO("Testing funds")
		D = 24 * 60 * 60

		maketime(buck, 0)
		update(buck)

		# receive 1000 REX
		transfer(eosio_token, user1, buck, "1.0000 EOS", "deposit")
		assertRaises(self, lambda: withdraw(buck, user1, "1000.0000 REX"))

		maketime(buck, D)

		# receive 999 REX
		transfer(eosio_token, user1, buck, "1.0000 EOS", "deposit")
		assertRaises(self, lambda: withdraw(buck, user1, "1000.0000 REX"))

		table(buck, "fund")

		# mature rex
		maketime(buck, D * 6)

		# withdraw 1000 REX
		withdraw(buck, user1, "1000.0000 REX")
		assertRaises(self, lambda: withdraw(buck, user1, "1000.0000 REX"))

		# mature rex
		maketime(buck, D * 6)

		# withdraw 999 REX
		withdraw(buck, user1, "999.0000 REX")
		assertRaises(self, lambda: withdraw(buck, user1, "998.0000 REX"))

		funds = table(buck, "fund", element="balance", row=1)
		self.assertEqual(0, amount(funds))


		


# main

if __name__ == "__main__":
	unittest.main()
