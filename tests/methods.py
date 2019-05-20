# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import unittest
from eosfactory.eosf import *
from functools import reduce
from datetime import datetime
import time

def timeMs(): return int(time.time()*1000.0)

# actions

def deploy(contract):
	if not contract.is_built():
		contract.build()
	contract.deploy()

def perm(contract, key):
	contract.set_account_permission(Permission.ACTIVE,
		{
			"threshold" : 1, "keys" : [{ "key": key.key_public, "weight": 1 }],
			"accounts": [{ "permission": { "actor": contract, "permission": "eosio.code" }, "weight": 1 }],
		},
		Permission.OWNER, (contract, Permission.OWNER))
	setup_oracle(contract, contract)

def setup_oracle(contract, oracle):
	contract.set_account_permission("admin",
		{
			"threshold" : 1, "keys" : [],
			"accounts": [{ "permission": { "actor": oracle, "permission": "active" }, "weight": 1 }],
		},
		Permission.ACTIVE, (contract, Permission.OWNER))
	contract.set_action_permission("buck", "forceupdate", "admin", (contract, Permission.ACTIVE))

def create_issue(contract, to, symbol):
	try:
		contract.push_action(force_unique=True, max_cpu_usage=30, action="create",
			data={ "issuer": to, "maximum_supply": "1000000000000.0000 {}".format(symbol) }, permission=[(contract, Permission.ACTIVE)])
	except: pass
	try:
		contract.push_action(force_unique=True, max_cpu_usage=30, action="issue",
			data={ "to": to, "quantity": "1000000000000.0000 {}".format(symbol), "memo": "" }, permission=[(to, Permission.ACTIVE)])
	except: pass

def destroy(contract):
	contract.push_action(force_unique=True, max_cpu_usage=10000, action="zdestroy", data="[]", permission=[(contract, Permission.ACTIVE)])

def transfer(contract, fromAccount, to, quantity, memo=""):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="transfer",
		data={
			"from": fromAccount,
			"to": to,
			"quantity": quantity,
			"memo": memo
		}, permission=[(fromAccount, Permission.ACTIVE)])

def buyram(contract):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="buyram", data="[]", permission=[(contract, Permission.ACTIVE)])

# contract actions

def open(contract, user, ccr, acr, quantity):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="open",
		data={
			"account": user,
			"dcr": ccr,
			"icr": acr,
			"quantity": quantity
		}, permission=[(user, Permission.ACTIVE)])

def update(contract, eos=200, runs=1):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="forceupdate", data={ "eos_price": eos }, permission=[(contract, "admin")])

	for i in range(0, runs + 2):
		run(contract)

def exchange(contract, user, quantity):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="exchange",
		data={
			"account": user, 
			"quantity": quantity,
		}, permission=[(user, Permission.ACTIVE)])

def close(contract, user, cdp_id):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="close", data={ "cdp_id": cdp_id }, permission=[(user, Permission.ACTIVE)])

def run(contract, max=50):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="run", data={ "max": max }, permission=[(contract, Permission.ACTIVE)])

def reparam(contract, user, cdp_id, change_debt, change_collat):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="change",
		data={
			"cdp_id": cdp_id,
			"change_debt": change_debt,
			"change_collateral": change_collat
		}, permission=[(user, Permission.ACTIVE)])

def changeacr(contract, user, cdp_id, acr):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="changeicr",
		data={
			"cdp_id": cdp_id,
			"icr": acr
		}, permission=[(user, Permission.ACTIVE)])

def redeem(contract, user, quantity):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="redeem",
		data={
			"account": user,
			"quantity": quantity
		}, permission=[(user, Permission.ACTIVE)])

def withdraw(contract, user, quantity):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="withdraw",
		data={
			"account": user,
			"quantity": quantity
		}, permission=[(user, Permission.ACTIVE)])

def save(contract, user, quantity):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="save",
		data={
			"account": user,
			"quantity": quantity
		}, permission=[(user, Permission.ACTIVE)])

def unsave(contract, user, quantity):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="unsave",
		data={
			"account": user,
			"quantity": quantity
		}, permission=[(user, Permission.ACTIVE)])

def maketime(contract, time):
	contract.push_action(force_unique=True, max_cpu_usage=30, action="zmaketime",
		data={ "seconds": time }, permission=[(contract, Permission.ACTIVE)])

def fundbalance(buck, user):
	return amount(table(buck, "fund", field="account", value=user, element="balance"))

def fundexbalance(buck, user):
	return amount(table(buck, "fund", field="account", value=user, element="exchange_balance"))

def get_cdp(buck, id, element=None): return table(buck, "cdp", buck, lower=id, upper=id, limit=1, element=element)
def get_debtors(buck, limit=1): return table(buck, "cdp", index=2, limit=limit, row=None, keytype="float64")
def get_liquidators(buck, limit=1): return table(buck, "cdp", index=3, limit=limit, row=None, keytype="float64")

# requests

def balance(token, account, unwrap=True):
	rows = token.table("accounts", account).json["rows"]
	if len(rows) == 0:
		return 0 if unwrap else "0 -"
	balance = rows[0]["balance"]
	if unwrap:
		return amount(balance, force=False)
	else:
		return balance

def amount(quantity, force=True, default=0):
	split = []
	if isinstance(quantity, str):
		split = quantity.split(" ")
	elif force: assert("value is not an asset")
	else: return default

	if isinstance(split, list):
		if len(split) == 2: 
			return float(split[0])
		elif force: assert("value is not an asset")
		else: return default
	assert("value is not an asset")

def asset(amount, symbol="EOS", precision=4):
	num = int(amount)
	n = num < 0
	a = str(abs(num))
	s = "0" if len(a) <= 4 else a[:len(a) - precision]
	e = a[-precision:]
	if len(e) < 4:
		e = "".join(list(map(lambda x: "0", range(0, 4-len(e))))) + e
	n = "-" if n else "" 
	return n + s + "." + e + " " + symbol

def unpack(value):
	return amount(asset(value))

# field and value - to query from given results
def table(contract, table, scope=None, row=0, element=None, field=None, index=1, keytype="i64", value=None, lower="", upper="", limit=10):
	if scope == None: scope = contract
	data = contract.table(table, scope, lower=str(lower), upper=str(upper), index=index, limit=limit, key_type=keytype).json["rows"]

	# query
	if field is not None and value is not None:
		if len(data) > 0:
			for s in data:
				if str(s[field]) == str(value):
					row = None
					data = s
	
	# row/element
	if row is not None and len(data) > 0: data = data[row]
	if element is not None: return data[element]
	else: return data

# assert

def assertErrors(self, tests):
	for test in tests:
		if isinstance(test, list) and len(test) == 2:
			assertRaisesMessage(self, test[0], test[1])
		else:
			assertRaises(self, test)

def assertRaisesMessage(self, message, func):
	with self.assertRaises(Error) as c:
		func()
	self.assertIn(message.lower(), c.exception.message.lower())
	print("+ Exception raised: \"%s\"" % message)

def assertRaises(self, func):
	with self.assertRaises(Error):
		func()
	print("+ Exception raised")