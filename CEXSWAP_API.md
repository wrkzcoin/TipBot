### CEXSwap Public API:
* Please refer to : <https://tipbot-public-api.cexswap.cc/manual>

### CEXSwap Private API:
First of all, you need to get a unique API key from TipBot by doing Direct Message `/cexswap apikey`. TipBot shall respond with a key and you save them in a safe place and you can reset anytime later with the same command but with extra option `resetkey` = YES. You need to be in our main Discord Guild <https://discord.com/invite/GpHzURM> to be able to execute this command.

#### Example with curl:
  * get_balance

  ```
  curl -H "Content-Type: application/json" -H "Authorization: xxxx" https://tipbot-private-api.cexswap.cc/get_balance/wrkz
  ```

  * get_address

  ```
  curl -H "Content-Type: application/json" -H "Authorization: xxxx" https://tipbot-private-api.cexswap.cc/get_address/wrkz
  ```

  * sell

  ```
  curl --header "Authorization: xxx" \
  --request POST \
  --data '{"method": "sell", "params": [{"amount": "10k", "sell_token": "wrkz", "for_token": "dego"}], "id": 99}' \
  https://tipbot-private-api.cexswap.cc
  ```

  ```
  {"success": true, "sell": "10,000", "sell_token": "WRKZ", "get": "956,782.68", "for_token": "DEGO", "price_impact_percent": 0.0, "message": "Successfully traded! Get 956,782.68 DEGO from selling 10,000 WRKZ Ref: JDQCMWXJMVJZAABI", "error": null, "time": 1675655061}
  ```

#### Other note:
Bot will reject your selling through API if you are not inside our Discord Guild. This is to easier troubleshooting in case there is any issue.
