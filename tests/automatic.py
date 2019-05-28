# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import unittest, random, string
from eosfactory.eosf import *
import eosfactory.core.setup as setup 
from methods import *
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

	def test(self):
		SCENARIO("Testing cdp logic")

		for cycle_i in range(1, 200):

			##################################
			COMMENT(f"Cycle {cycle_i}")

			try:
				transfer(eosio_token, buck, user1, "100000000.0000 EOS", "")
			except: pass

			destroy(buck)
			maketime(buck, 0)
			update(buck, 1)

			transfer(eosio_token, user1, buck, "100000000.0000 EOS", "deposit")

			initial_funds = fundbalance(buck, user1)

			# mature rex
			test.init()
			maketime(buck, test.time)
			update(buck, test.price)

			##################################
			COMMENT("Open CDP")

			for cdp in sorted(test.table, key=lambda x:int(x.id)):
				ccr = int(0 if cdp.cd > 999999 else cdp.cd)
				open(buck, user1, ccr, cdp.acr, asset(cdp.collateral, "REX"))

			##################################
			COMMENT("Initial matching")
			
			self.compare(buck, test.table)

			##################################
			COMMENT("Start rounds")

			rounds = 20
			for round_i in range(1, rounds):
				print("\n\n\n\n")
				COMMENT(f"Round {round_i} / {rounds} of cycle {cycle_i}")

				# actions
				result = test.run_round(balance(buck, user1) * 10000)
				round_time = result[0]
				actions = result[1]

				if len(actions) == 0:
					COMMENT("No actions were performed")
				else:
					for action in actions:
						if action[0][0] == "reparam":
							cdp = action[0][1]
							col = asset(action[0][2], "REX")
							debt = asset(action[0][3], "BUCK")

							# print("reparam", col, debt)
							if action[1] == False:
								assertRaises(self, lambda: reparam(buck, user1, cdp, debt, col))
							else: reparam(buck, user1, cdp, debt, col)

						elif action[0][0] == "acr":
							cdp = action[0][1]
							acr = action[0][2]

							if action[1] == False:
								assertRaises(self, lambda: changeacr(buck, user1, cdp, acr))
							else: changeacr(buck, user1, cdp, acr)

						elif action[0][0] == "redeem":

							quantity = asset(action[0][1], "BUCK")

							if action[1] == False:
								balance(buck, user1)
								assertRaises(self, lambda: redeem(buck, user1, quantity))
							else: redeem(buck, user1, quantity)

				maketime(buck, round_time)
				update(buck, test.price, 3)
				
				##################################
				COMMENT(f"Matching after round {round_i}")

				# match cdps
				self.compare(buck, test.table)

				# match taxes
				taxation = table(buck, "taxation")
				self.assertAlmostEqual(unpack(test.IDP), amount(taxation["insurance_pool"]), 3, "insurance pools don't match")
				self.assertAlmostEqual(unpack(test.TEC), unpack(taxation["total_excess"]), 0, "total excesses don't match")
				self.assertAlmostEqual(unpack(test.CIT), amount(taxation["collected_excess"]), 0, "collected insurances don't match")
				# self.assertAlmostEqual(unpack(test.AEC), unpack(taxation["aggregated_excess"]), 0, "aggregated excesses don't match") # uint128 doesn't parse
				print("+ Matched insurance pools")

				# match buck supply
				supply = amount(table(buck, "stat", "BUCK", element="supply"))
				user_balance = balance(buck, "user1")
				scruge_balance = balance(buck, "equityscruge")
				collected_savings = amount(taxation["collected_savings"])
				savings_pool = amount(taxation["savings_pool"])
				locked_in_requests = self.get_locked_in_requests_tokens()
				circulation = scruge_balance + user_balance + collected_savings + savings_pool + locked_in_requests
				self.assertAlmostEqual(supply, circulation, 4, "supply doesn't match total buck")
				print("+ Matched buck supply")

				# match funds + collateral
				total_collateral = 0
				for cdp in test.table:
					total_collateral += cdp.collateral / 10000

				insurance_pool = amount(taxation["insurance_pool"])
				collected_insurance = amount(taxation["collected_excess"])
				scruge_funds = fundbalance(buck, "scrugescruge")
				current_balance = fundbalance(buck, "user1")
				calculated_funds = insurance_pool + scruge_funds + total_collateral + current_balance + collected_insurance
				self.assertAlmostEqual(initial_funds, calculated_funds, 3, "total funds don't match")
				print("+ Matched rex supply")


				##################################
				COMMENT(f"Round {round_i} / {rounds} of cycle {cycle_i} complete.")


	def get_locked_in_requests_tokens(self):
		tokens = 0
		redeem = table(buck, "redeemreq", row=None)
		for req in redeem:
			tokens += amount(req["quantity"])
		reparam = table(buck, "reparamreq", row=None)
		for req in reparam:
			debt = amount(req["change_debt"])
			if debt < 0: tokens += debt 
		return tokens

	def compare(self, buck, cdp_table):
		print("debtors")
		test.print_table()
		top_debtors = get_debtors(buck, limit=100)
		for i in range(0, len(top_debtors)):
			debtor = top_debtors[i]
			if amount(debtor["debt"]) == 0: break # unsorted end of the table
			cdp = test.table[i * -1 - 1]
			self.match(cdp, debtor)

		test_liquidators = sorted(test.table, key=test.liq_sort)
		print("liquidators")
		test.print_table(test_liquidators)
		top_liquidators = get_liquidators(buck, limit=100)
		for i in range(0, len(top_liquidators)):
			liquidator = top_liquidators[i]
			if liquidator["icr"] == 0: break # unsorted end of the table
			cdp = test_liquidators[i]
			self.match(cdp, liquidator)

	def match(self, cdp, row):
		print(cdp)
		print("#" + str(row["id"]), row["collateral"], row["debt"], row["icr"])

		self.assertEqual(cdp.id, row["id"], "attempt to match different CDPs")
		self.assertEqual(cdp.acr, row["icr"], "ACRs don't match")		
		self.assertAlmostEqual(unpack(cdp.debt), amount(row["debt"]), 3, "debts don't match")
		self.assertAlmostEqual(unpack(cdp.collateral), amount(row["collateral"]), 3, "collaterals don't match")
		self.assertEqual(cdp.time, row["modified_round"], "rounds modified don't match")

		print(f"+ Matched cdp #{cdp.id}")


# main

if __name__ == "__main__":
	unittest.main()
