// Copyright © Scruge 2019.
// This file is part of BUCK Protocol.
// Created by Yaroslav Erohin and Dmitry Morozov.

inline void buck::inline_transfer(const name& account, const asset& quantity, const std::string& memo, const name& contract) {
	action(permission_level{ _self, "active"_n },
		contract, "transfer"_n,
		std::make_tuple(_self, account, quantity, memo)
	).send();
}
