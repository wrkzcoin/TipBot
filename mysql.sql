CREATE TABLE `wrkz_donate` (
  `from_user` varchar(32) NOT NULL,
  `to_address` varchar(128) NOT NULL,
  `amount` bigint(20) NOT NULL,
  `date` int(11) NOT NULL,
  `tx_hash` varchar(64) NOT NULL,
  KEY `from_user` (`from_user`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_send` (
  `from_user` varchar(32) NOT NULL,
  `to_address` varchar(256) NOT NULL,
  `amount` bigint(20) NOT NULL,
  `date` int(11) NOT NULL,
  `tx_hash` varchar(64) NOT NULL,
  `paymentid` varchar(64) DEFAULT NULL,
  KEY `from_user` (`from_user`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_tag` (
  `tag_id` varchar(32) CHARACTER SET utf8mb4 NOT NULL,
  `tag_desc` varchar(2048) CHARACTER SET utf8mb4 NOT NULL,
  `date_added` int(11) NOT NULL,
  `tag_serverid` varchar(32) NOT NULL,
  `added_byname` varchar(32) CHARACTER SET utf8mb4 NOT NULL,
  `added_byuid` varchar(32) NOT NULL,
  `num_trigger` int(11) NOT NULL DEFAULT '0',
  KEY `tag_id` (`tag_id`),
  KEY `tag_serverid` (`tag_serverid`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_tip` (
  `from_user` varchar(32) NOT NULL,
  `to_user` varchar(32) NOT NULL,
  `amount` bigint(20) NOT NULL,
  `date` int(11) NOT NULL,
  `tx_hash` varchar(64) NOT NULL,
  KEY `from_user` (`from_user`),
  KEY `to_user` (`to_user`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_tipall` (
  `from_user` varchar(32) NOT NULL,
  `amount_total` bigint(20) NOT NULL,
  `date` int(11) NOT NULL,
  `tx_hash` varchar(64) NOT NULL,
  KEY `from_user` (`from_user`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_user` (
  `user_id` varchar(32) NOT NULL,
  `balance_wallet_address` varchar(128) NOT NULL,
  `user_wallet_address` varchar(128) DEFAULT NULL,
  `balance_wallet_address_ts` int(11) DEFAULT NULL,
  `balance_wallet_address_ch` int(11) DEFAULT NULL,
  `lastOptimize` int(11) DEFAULT NULL,
  `privateSpendKey` varchar(64) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`),
  KEY `balance_wallet_address` (`balance_wallet_address`),
  KEY `user_wallet_address` (`user_wallet_address`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_walletapi` (
  `balance_wallet_address` varchar(128) NOT NULL,
  `actual_balance` bigint(20) NOT NULL DEFAULT '0',
  `locked_balance` bigint(20) NOT NULL DEFAULT '0',
  `lastUpdate` int(11) DEFAULT NULL,
  UNIQUE KEY `balance_wallet_address` (`balance_wallet_address`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

CREATE TABLE `wrkz_withdraw` (
  `user_id` varchar(32) NOT NULL,
  `amount` bigint(20) NOT NULL,
  `to_address` varchar(128) DEFAULT NULL,
  `date` int(11) NOT NULL,
  `tx_hash` varchar(64) NOT NULL,
  KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;