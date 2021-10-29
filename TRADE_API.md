### Public API for Trading:
* List of open markets: <https://public-trade-api.bot.tips/markets>
* Market Information of a Ticker. Example: <https://public-trade-api.bot.tips/ticker/wrkz>
* List of opened buy and sell orders. Example: <https://public-trade-api.bot.tips/orders/gntl-xmr>

### Private API for Trading:
First of all, you need to get api user/keys from TipBot by doing Direct Message `.acc tradeapi`. TipBot shall respond with keys and save them in a safe place. You can also reset the API key with command `.acc tradeapi regen`.

[<img src="https://raw.githubusercontent.com/wrkzcoin/TipBot/multi-tipbot/docs/acc_tradeapi.png">](http://invite.discord.bot.tips/)


* Example with curl
  * get_balance (get your deposit address, same as you got in Discord)

  ```curl -H "Content-Type: application/json" -H "Authorization-User: xxxx" -H "Authorization-Key: yyyy" https://private-api.bot.tips/get_balance/wrkz```
  
  * deposit (get your deposit address, same as you are having in Discord)


  ```curl -H "Content-Type: application/json" -H "Authorization-User: xxxx" -H "Authorization-Key: yyyy" https://private-api.bot.tips/deposit/wrkz```
  
  * buy

  ```curl -d '{"ref_number": "100XXXX"}' -X POST -H "Content-Type: application/json" -H "Authorization-User: xxxx" -H "Authorization-Key: yyyy" https://private-api.bot.tips/buy```

  * sell

  ```curl -d '{"coin_sell": "GNTL", "coin_get": "XMR", "amount_sell": "1,000.0", "amount_get": "0.006"}' -X POST -H "Content-Type: application/json" -H "Authorization-User: xxxx" -H "Authorization-Key: yyyy" https://private-api.bot.tips/sell```

  * cancel

  ```curl -d '{"ref_number": "100XXXX"}' -X POST -H "Content-Type: application/json" -H "Authorization-User: xxxx" -H "Authorization-Key: yyyy" https://private-api.bot.tips/cancel```
