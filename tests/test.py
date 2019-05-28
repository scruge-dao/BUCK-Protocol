# coding: utf8
# Copyright © Scruge 2019.
# This file is part of Buck Protocol.
# Created by Yaroslav Erohin.

import random
from math import exp

table = []
CR = 150 # collateral ratio
LF = 10 # Liquidation Fee
IR = 20 # insurance ratio
SR = 100 - IR # savings ratio
r = 0.095 # interest rate
IDP = 0 # insurance dividend pool
TEC = 0 # total excess collateral
AEC = 0 # aggregated excess collateral
CIT = 0 # collected insurance tax
commission = 20 # our commission
time = 0 # initial time
oracle_time = 0

MIN_DEBT = 10_0000
MIN_COLLATERAL = 5_0000
MIN_INSURER_REX = 5_0000_0000

def time_now():
	global time
	time += random.randint(1, 1440) * 60 # minutes
	return time

def epsilon(value): return 0 # value / 500

class CDP:
	def __init__(self, collateral, debt, cd, acr, id, time):
		self.collateral = int(collateral)
		self.debt = int(debt)
		self.cd = cd
		self.acr = acr
		self.id = id
		self.time = time
	def __repr__(self):
		string = "c: " + str(int(self.collateral // 10000)) + "."  + str(int(self.collateral % 10000))
		string2 = "d: " + ("0\t" if self.debt == 0 else (str(int(self.debt // 10000)) + "." + str(int(self.debt % 10000))))
		return "#" + str(self.id)  + "\t" + string + "\t" + string2  + "\t" + "icr: " + str(self.acr) + "\tcd: " + str(self.cd) + "\t" + "\tacr:" + str(self.acr) + "\ttime: " + str(self.time)


	def add_debt(self,new_debt):
		self.debt = self.debt + int(new_debt)
	def add_collateral(self, new_collateral):
		self.collateral = int(self.collateral) + int(new_collateral)
	def new_cd(self, cd_new):
		self.cd = cd_new
	def new_acr(self,acr_new):
		self.acr = int(acr_new)
	def new_debt(self, debt_new):
		self.debt = int(debt_new)
	def new_collateral(self, collateral_new):
		self.collateral = int(collateral_new)
	def new_time(self, time_new):
		self.time = time_new		

# Functions for generation of sorted CDPs with random values

def generate_liquidators(k):
	global TEC, time
	rand = random.randrange(5_0000_0000, 1000_0000_0000, 1)
	rand2 = random.randint(150, 500)
	liquidator = CDP(rand, 0, 9999999, rand2, 0, time)
	TEC += liquidator.collateral * 100 // liquidator.acr
	liquidators = [liquidator]
	for i in range (0,k):
		rand = random.randrange(5_0000_0000, 1000_0000_0000, 1)
		helper = liquidators[i].acr
		rand2 = random.randint(helper+1,helper+2)
		liquidators.append(CDP(rand, 0, 9999999, rand2,i+1, time))
		liquidator = liquidators[len(liquidators)-1]
		TEC += liquidator.collateral * 100 // liquidator.acr
	return liquidators

def generate_debtors(k, n):
	global time, price
	rand = random.randrange(5_0000_0000, 1000_0000_0000, 1) # collateral
	rand2 = random.randint(150, 500) # cd
	ccr = rand2
	debtor = CDP(rand, 0, rand2, 0, k+1, time)
	debtor.add_debt(debtor.collateral * price // debtor.cd)
	debtor.new_cd(debtor.collateral * price / debtor.debt)
	debtors = [debtor]
	for i in range (k+1,n):
		rand = random.randrange(5_0000_0000, 1000_0000_0000, 1)
		helper = ccr
		acr = random.randint(100, 160)
		if acr < 150: acr = 0
		rand2 = random.randint(helper+1, helper + 2)
		ccr = rand2
		debtor = CDP(rand, 0, rand2, acr, i+1, time)
		debtor.add_debt(debtor.collateral * price // debtor.cd)	
		debtor.new_cd(debtor.collateral * price / debtor.debt)
		debtors.insert(0, debtor)
	return debtors

def gen(k, n):
	global table, time, price
	liquidators = generate_liquidators(k)
	debtors = generate_debtors(k, n)
	table = sorted(liquidators + debtors, key=deb_sort)

# Function for inserting CDP into the table

def cdp_insert(cdp): # add id primary sorting to all debtors
	global table
	table.append(cdp)
	table = sorted(table, key=deb_sort)

# Function for pulling out CDP from the table by querying its ID
def cdp_index(id):
	global table

	if len(table) == 0:
		return -1

	for i in range(0, len(table)):
		if table[i].id == id:
			return i
	return -1

def print_table(t=None):
	global table
	if t == None: t = table
	if t == []:
		print("table is empty")
	else:
		print("\nfull table:")
		for i in range(0,len(t)):
			print(t[i])
	print("---")

# Helper functions for calculations

def calc_ccr(cdp, price):
	ccr = cdp.collateral * price // cdp.debt
	return int(ccr)

def calc_lf(cdp, price, cr, lf):
	ccr = calc_ccr(cdp, price)
	if ccr >= 100 + lf:
		l = lf
	elif ccr < 75:
		l = -25
	else: 
		l = ccr - 100
	return l


def calc_bad_debt(cdp, price, cr, lf):
	ccr = calc_ccr(cdp, price)
	val = (cr*cdp.debt-cdp.collateral * price) // (cr - 100 - lf)
	return int(val)

def calc_val(cdp, liquidator, price, cr, lf):
	l = calc_lf(cdp, price, cr, lf)
	c = liquidator.collateral
	d = liquidator.debt
	acr = int(liquidator.acr)
	bad_debt = calc_bad_debt(cdp, price, cr, l)
	bailable = ((c*price)-(d*acr)) * (100-l) // (acr*(100-l)-10_000)
	# print("bad_debt", bad_debt)
	# print("bailable", bailable)
	return min(bad_debt, bailable, cdp.debt)

# Taxes

def add_tax(cdp, price, m=False):
	global IDP, CIT, TEC, oracle_time

	if cdp.debt == 0 or cdp.collateral > MIN_INSURER_REX and cdp.debt <= MIN_DEBT: 
		return cdp

	if oracle_time == cdp.time:
		return cdp

	dm = 1000000000000
	v = int((exp((r*(oracle_time-cdp.time))/31_557_600) -1) * dm)
	interest = int(cdp.debt * v) // dm

	minimum = 0 if m == False else 1
	accrued_debt = max(minimum, interest * SR // 100)
	accrued_col = (max(minimum, (interest * IR // price)))

	print("add tax", cdp)
	cdp.add_debt(accrued_debt)
	cdp.add_collateral(-accrued_col)
	cdp.new_cd(cdp.collateral * 100 / cdp.debt)
	cdp.new_time(oracle_time)
	CIT += accrued_col

	print(accrued_debt, accrued_col)
	print(cdp)
	return cdp

def update_tax(cdp, price, m=False):
	cdp = add_tax(cdp, price, m)
	global IDP, AEC, CIT, TEC, oracle_time
	if AEC > 0 and cdp.debt <= epsilon(cdp.debt):
		if oracle_time != cdp.time:
			ec = cdp.collateral * 100 // cdp.acr 
			AGEC = ec * (oracle_time-cdp.time) # aggregated by this user
			dividends = IDP * AGEC // AEC
			AEC -= AGEC
			IDP -= dividends
			cdp.add_collateral(dividends)
			cdp.new_time(oracle_time)
	return cdp

# Contract functions

def liq_sort(x): return ls(x.collateral, x.debt, x.acr, x.id)
def deb_sort(x): return ds(x.collateral, x.debt, x.id)

def ds(collateral, debt, id): # in reverse
	MAX = 100_000_000_000_000_000_000

	if debt == 0 or collateral == 0:
		return - id / 10000

	cd = collateral * 10_000_000_000_000 // debt
	return (MAX - cd)    + id / 10000

def ls(collateral, debt, acr, id):
	MAX = 100_000_000_000_000_000_000

	if acr == 0 or collateral == 0:
		return (MAX * 3)    + id / 10000

	if debt <= MIN_DEBT and collateral > MIN_INSURER_REX:
		return (MAX - collateral * 10_000 // acr)   - id / 10000

	if debt == 0: return MAX * 4

	cd = collateral * 10_000_000_000_000 / debt
	return (MAX * 2 - cd // acr)   + id / 10000

def is_insurer(cdp):
	return not (cdp.acr == 0 or cdp.debt > MIN_DEBT or (cdp.debt < MIN_DEBT and cdp.collateral < MIN_INSURER_REX))

def liquidation(price, cr, lf):	
	print("liquidation")
	global TEC, table
	if table == []: return
	# i = 0

	while True:

		liquidators = sorted(table, key=liq_sort)
		# print("liquidators")
		# print_table(liquidators)

		debtor = table.pop(len(table)-1)
		idx = cdp_index(liquidators[0].id)

		# if i >= len(table) or debtor.id == table[idx].id: 
		# 	cdp_insert(debtor)

			# print("\n\n")
			# print(f"liquidator", table[idx])
			# print("debtor", debtor)
			# print("FAILED: END")
			# return # failed

		debtor = add_tax(debtor, price)

		print("\nliquidator\n", table[idx])
		print("debtor\n", debtor)

		if debtor.debt <= epsilon(debtor.debt):
			cdp_insert(debtor)
			# print("DONE1")
			return # done

		if debtor.collateral * price // debtor.debt >= CR  - epsilon(CR):
			cdp_insert(debtor)
			# print("DONE2")
			return # done
	
		if table[idx].acr == 0:
			# print(table[idx])
			# print("NO ACR\n")
			cdp_insert(debtor)
			return

		liquidator = table.pop(idx)

		if is_insurer(liquidator):
			TEC -= liquidator.collateral * 100 // liquidator.acr
		liquidator = update_tax(liquidator, price)

		liq_ccr = 9999999

		if liquidator.debt > epsilon(liquidator.debt):
			liq_ccr = liquidator.collateral * price // liquidator.debt

		if liq_ccr < CR or liquidator.debt > epsilon(liquidator.debt) and liq_ccr <= liquidator.acr:
			# print("FAILED: NO MORE GOOD LIQUIDATORS\n")
			cdp_insert(liquidator)
			cdp_insert(debtor)
			return

		l = calc_lf(debtor, price, cr, lf)
		use_d = calc_val(debtor, liquidator, price, cr,l) # use debt
		use_c = min((use_d * (100+lf) // price), debtor.collateral) # use col

		debtor.add_debt(-use_d)
		debtor.add_collateral(-use_c)
		liquidator.add_debt(use_d)
		liquidator.add_collateral(use_c)

		if debtor.debt <= epsilon(debtor.debt):
			debtor.new_cd(9999999)
		else:
			debtor.new_cd(debtor.collateral * 100 / debtor.debt)

		if is_insurer(liquidator):
			TEC += liquidator.collateral * 100 // liquidator.acr
			liquidator.new_cd(9999999)
		else:
			liquidator.new_cd(liquidator.collateral * 100 / liquidator.debt)

		cdp_insert(liquidator)

		if debtor.debt > 0:
			cdp_insert(debtor)
		# else:
			# print("removing debtor", debtor.id)
		# i = 0
		# print(".\n")

def redemption(amount, price):
	global time, table
	i = len(table)-1

	# print_table()

	print("\n\nredeem", amount)

	debtors_failed = 0
	while amount > epsilon(amount) and i != -1 and debtors_failed < 30:
		cdp = table.pop(i)
		print(cdp)
		cdp = add_tax(cdp, price)

		print(cdp)

		if cdp.debt < 500000 + epsilon(500000):
			cdp_insert(cdp)
			i -= 1
			debtors_failed += 1
			print("debtor failed debt", debtors_failed)
			continue

		rf = 1
		if cdp.collateral * price // cdp.debt < 100 - rf:
			cdp_insert(cdp)
			i -= 1
			debtors_failed += 1
			print("debtor failed ccr", debtors_failed)
			continue

		if cdp.debt > amount:
			c = (amount * 100) // (price * (100 + rf) // 100)
			d = amount

			# print(cdp)
			cdp.add_debt(-d)
			cdp.add_collateral(-c)
			cdp.new_cd(cdp.collateral * 100 / cdp.debt)
			cdp_insert(cdp)
			amount = 0

			print("redeem updating", cdp.id, c, d)
			print(cdp)
		else:
			d = cdp.debt
			c = (d * 100) // (price * (100 + rf) // 100)

			# print(cdp)
			cdp.new_debt(0)
			cdp.add_collateral(-c)

			print("redeem removing", cdp.id, c, d)
			print(cdp)

			amount -= d
			i -= 1
	print("redeem left over", amount)
	return

def reparametrize(id, c, d, price):
	global TEC, table, CR 
	cr = CR

	idx = cdp_index(id)
	if table[idx].id != id:
		return

	cdp = table.pop(idx)
	print("reparam", cdp)

	if is_insurer(cdp):
		TEC -= cdp.collateral * 100 // cdp.acr

	cdp = update_tax(cdp, price)
	# print(cdp)

	if d < 0:
		if cdp.debt + d >= 50000 + epsilon(50000):
			cdp.add_debt(d)
		# else: print("not removing d below min")

	if c > 0:
		cdp.add_collateral(c)

	if c < 0:
		if cdp.debt == 0:
			cdp.add_collateral(c)
			# print("change c", c)
		else:
			ccr = calc_ccr(cdp, price)
			if ccr < cr:
				pass
			else:
				m = cdp.collateral - (cdp.debt * cr) // price
				cdp.add_collateral(max(c, -m))
				# print("deb", cdp.debt)
				# print("col", cdp.collateral)
				# print("price", price)
				# print("m", m)
				# print("change c", max(c, -m))

	if d > 0:
		if cdp.debt == 0:
			# print("max d", cdp.collateral * price // cr)
			# print("new c", cdp.collateral)
			cdp.add_debt(min(d, cdp.collateral * price // cr))
		else:
			# print("ccr", calc_ccr(cdp, price))
			if calc_ccr(cdp, price) < cr:
				pass
			else:
				val = (cdp.collateral * price * 100 // (cr * cdp.debt) - 100) * cdp.debt // 100
				cdp.add_debt(min(d, val))
	
	if cdp.debt != 0:
		cdp.new_cd(cdp.collateral * 100 / cdp.debt)
	else:
		cdp.new_cd(9999999)

	if is_insurer(cdp):
		TEC += cdp.collateral * 100 // cdp.acr
	cdp_insert(cdp)
	print("done", cdp, "\n")

def change_acr(id, acr):
	global TEC, table, oracle_time, price
	if acr < CR or acr > 100000:
		return False

	print("acr...")
	cdp = table.pop(cdp_index(id))

	if cdp.acr == acr:
		cdp_insert(cdp)
		return False

	if is_insurer(cdp):
		TEC -= (cdp.collateral * 100 // cdp.acr)

	cdp = update_tax(cdp, price)
	cdp.new_acr(acr)

	if is_insurer(cdp):
		TEC += (cdp.collateral * 100 // cdp.acr)

	cdp_insert(cdp)

		
def update_round():
	global AEC, IDP, CIT, oracle_time, time, TEC, price
	val1 = TEC * (time - oracle_time)
	AEC += val1
	val2 = (CIT - (CIT * commission) // 100)
	IDP += val2
	CIT = 0
	oracle_time = time

# returns [time, [{action, failed?}], table]
def run_round(balance):
	global time, CR, LF, IR, r, SR, IDP, TEC, CIT, time, oracle_time, price, table

	LIQUIDATION = True
	REDEMPTION 	= True
	ACR 		= True
	REPARAM 	= True

	actions = []
	old_price = price
	length = len(table)
	if length == 0: return [time, actions]

	# acr requests get processed immediately
	if ACR and length > 1:
		k = 10
		for i in range(0, random.randint(1, length-1)):
			if cdp_index(i) != -1:
				acr = random.randint(148, 300)
				failed = change_acr(i, acr)
				actions.append([["acr", i, acr], failed != False])
				k -= 1
			if k == 0:
				break

	# create reparam requests
	reparam_values = [] # [i, c, d, success]
	if REPARAM and length > 1:
		k = 10
		for i in range(0, random.randint(1, length-1)):
			idx = cdp_index(i) 
			if idx != -1:
				c = random.randrange(-100_0000, 1000_0000)
				d = random.randrange(-100_0000, 1000_0000)

				# verify change with old price first (request creation step)
				cdp = table.pop(idx)
				new_col = cdp.collateral + c
				new_debt = cdp.debt + d
				new_ccr = 9999999
				if new_debt > 0: new_ccr = new_col * old_price // new_debt
				success = new_ccr >= CR and new_col >= MIN_COLLATERAL and (new_debt >= MIN_DEBT or new_debt == 0)
				if not success:
					print("--- was d. c", cdp.debt, cdp.collateral)
					print("reparam values:", new_ccr, new_col, new_debt)
				else: cdp = add_tax(cdp, price, True)
				reparam_values.append([i, c, d, success])
				cdp_insert(cdp)
				k -= 1
			if k == 0:
				break

	new_price = random.randint(-price // 10, price // 10) if LIQUIDATION else 1
	if new_price == 0: new_price = 100
	price += new_price

	time_now()
	update_round()

	print(f"<<<<<<<<\nnew time: {time}, price: {price} (last price: {old_price})\n")

	# other requests get processed after oracle update

	if price < old_price:
		liquidation(price, 150, 10)
		length = len(table)
		if length == 0: return [time, actions]

	for values in reparam_values:
		i = values[0]
		c = values[1]
		d = values[2]
		success = values[3]
		if success: 
			reparametrize(i, c, d, price)
		actions.append([["reparam", i, c, d], success])

	if REDEMPTION:
		v1 = random.randrange(25_0000, 10_000_0000)
		success = v1 <= balance
		if success: redemption(v1, price)
		actions.append([["redeem", v1], success])

	# accrue taxes
	new_table = table.copy()
	table = []
	for cdp in new_table:
		if oracle_time - cdp.time > 1314900:
			cdp = add_tax(cdp, price)
		cdp_insert(cdp)

	return [time, actions]

def init():
	global table, IDP, TEC, AEC, CIT, time, oracle_time, price
	
	table = []
	IDP = 0 # insurance dividend pool
	TEC = 0 # total excess collateral
	AEC = 0 # aggregated excess collateral
	CIT = 0 # collected insurance tax
	time = 0 # initial time

	price = random.randint(500, 1000)

	x = 10
	d = random.randint(x, x * 3)
	l = random.randint(int(d * 2), int(d * 5))
	time = 3000000
	oracle_time = time

	gen(x, l)

	print(f"<<<<<<<<\nstart time: {time}, price: {price}\n")
