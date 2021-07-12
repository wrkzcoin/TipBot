<?php
//ini_set('display_errors', 1);
//ini_set('display_startup_errors', 1);
//error_reporting(E_ALL);

// Turn off all error reporting
error_reporting(0);

$configs = include('config.php');

$dbhost = $configs['mysql_host'];
$dbport = $configs['mysql_port'];
$dbname = $configs['mysql_dbname'];
$dbusername = $configs['mysql_user'];
$dbpassword = $configs['mysql_password'];
$discord_webhook = $configs['discord_webhook'];

function post_discord ($titlename, $message) {
    global $discord_webhook;
    $ch = curl_init();

    curl_setopt($ch, CURLOPT_URL, $discord_webhook);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, "{\"username\": \"".$titlename."\", \"content\": \"".$message."\"}");

    $headers = array();
    $headers[] = 'Content-Type: application/json';
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        echo 'Error:' . curl_error($ch);
    }
    curl_close($ch);
}


function checkSecret_if_pending ($sec) {
   //Connecting to Redis server on localhost 
   $redis = new Redis(); 
   $redis->connect('127.0.0.1', 6379); 

   $get_pending = $redis->get($sec);
   if ($get_pending == "PENDING")
   {
       return TRUE;
   }
   else
   {
       //set the data in redis string 
       $redis->set($sec, "PENDING", 120); // 120s to expire 
       return FALSE;
   }
}


function updateStatusClaim ($claimed_address, $tx_hash, $sec) {
    global $dbhost, $dbname, $dbusername, $dbpassword, $dbport;
    $link = new PDO("mysql:host=$dbhost;dbname=$dbname;port=$dbport", $dbusername, $dbpassword);
    $stmt = $link->prepare("UPDATE cn_voucher SET already_claimed=?, claimed_address=?, claimed_date=?, tx_hash=? WHERE secret_string=?;");
    $stmt->execute(['YES', $claimed_address, round(microtime(true)), $tx_hash, $sec]);
    if(!$stmt)
    {
        die("Execute query error.");
    }
}

// Function to check string starting 
// with given substring 
function startsWith ($string, $startString) 
{ 
    $len = strlen($startString); 
    return (substr($string, 0, $len) === $startString); 
} 


function validate_doge($address, $coin_name) {
    global $configs;
    $ch = curl_init();

    $url = "http://".$configs['dogerpc_user'].":".$configs['dogerpc_password']."@".$configs['doge_rpcurl'];
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_TIMEOUT, 120); //timeout in seconds
    curl_setopt($ch, CURLOPT_POSTFIELDS, "{\"jsonrpc\": \"1.0\", \"id\":\"curltest\", \"method\": \"validateaddress\", \"params\": [\"".$address."\"] }");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);

    $headers = array();
    $headers[] = 'Content-Type: text/plain;';
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        echo 'Error:' . curl_error($ch);
    }
    curl_close($ch);
    $data_json = json_decode($result, true);
    $test = $data_json['result'];
    try {
        if (array_key_exists('isvalid', $test)) {
            if ($test['isvalid'] === TRUE) {
                return TRUE;
            } else {
                return FALSE;
            }
        } else {
            return FALSE;
        }
    } catch (Exception $e) {
        return FALSE;
    }
}

// Function send coin DOGE
function send_coin_doge($toAddr, $amount, $coin_name) {
    global $configs;
    $ch = curl_init();
    $url = "http://".$configs['dogerpc_user'].":".$configs['dogerpc_password']."@".$configs['doge_rpcurl'];
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_TIMEOUT, 120); //timeout in seconds
    curl_setopt($ch, CURLOPT_POSTFIELDS, "{\"jsonrpc\": \"1.0\", \"id\":\"curltest\", \"method\": \"sendtoaddress\", \"params\": [\"".$toAddr."\", ".$amount.", \"\", \"\"] }");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);


    $headers = array();
    $headers[] = 'Content-Type: text/plain;';
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        $post_to_discord = post_discord("TipBot-Voucher-CURL-".$coin_name, curl_error($ch));
        echo 'Error:' . curl_error($ch);
    }
    curl_close($ch);
    $data_json = json_decode($result, true);
    $transactionHash = $data_json['result'];
    if (!empty($transactionHash)) {
        // 64 characters
        if(strlen($transactionHash) !== 64) return FALSE;
    } else {
        return FALSE;
    }
    return $transactionHash;
}


function validate_xmr_fam($address, $coin_name) {
    global $configs;
    $ch = curl_init();
    if ($coin_name == 'GNTL')
    {
        if (
            substr($address, 0, 3) != 'gnt' ||
            !ctype_alnum(substr($address, 1)) ||
            (strlen($address) != 98 && strlen($address) != 99 && strlen($address) != 109)
        ) {
            return FALSE;
        }
        return TRUE;
    } elseif ($coin_name == 'WOW')
    {
        if (
            (substr($address, 0, 2) != 'WW' && substr($address, 0, 2) != 'Wo' && substr($address, 0, 2) != 'So') ||
            !ctype_alnum(substr($address, 1)) ||
            (strlen($address) != 97 && strlen($address) != 108)
        ) {
            return FALSE;
        }
        return TRUE;
    }
}

function validate_address($address, $coin_name) {
    global $configs;
    $ch = curl_init();
    $action = '/addresses/validate';
    if (($coin_name == 'TRTL') || ($coin_name == 'WRKZ') || ($coin_name == 'DEGO') || ($coin_name == 'BTCMZ'))
    {
        $header = $configs['walletheader_'.strtolower($coin_name)];
        $url =  $configs['walletrpc_'.strtolower($coin_name)];
    }

    curl_setopt($ch, CURLOPT_URL, $url . $action);
    curl_setopt($ch, CURLOPT_TIMEOUT, 90); //timeout in seconds
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, "{\"address\": \"".$address."\"}");
    curl_setopt($ch, CURLOPT_POST, 1);

    $headers = array();
    $headers[] = "Accept: application/json";
    $headers[] = "X-API-KEY: ".$header;
    $headers[] = "Content-Type: application/x-www-form-urlencoded";
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    $httpcode = intval(curl_getinfo($ch, CURLINFO_HTTP_CODE));

    if (curl_errno($ch)) {
        // echo 'Error:' . curl_error($ch);
        $post_to_discord = post_discord("TipBot-Voucher-CURL-".$coin_name, curl_error($ch));
        die("Internal error. Please report to us. Error code 1005. Failed validate address.");
    }
    curl_close ($ch);
            
    if ($httpcode == 200) {
        return TRUE;
    } else {
        return FALSE;
    }
}


// Function for sending Coin
function send_coin_xmr_fam($toAddr, $amount, $coin_name) {
    global $configs;
    $ch = curl_init();
    if ($coin_name == 'GNTL' || $coin_name == 'WOW')
    {
        $url =  $configs['walletrpc_'.strtolower($coin_name)];
    }

    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_TIMEOUT, 180); //timeout in seconds
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"transfer\",\"params\":{\"destinations\":[{\"amount\":".$amount.",\"address\":\"".$toAddr."\"}],\"account_index\":0,\"subaddr_indices\":[],\"priority\":1,\"unlock_time\":0,\"get_tx_key\": true}}");
    curl_setopt($ch, CURLOPT_POST, 1);

    $headers = array();
    $headers[] = "Accept: application/json";
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        // echo 'Error:' . curl_error($ch);
        $post_to_discord = post_discord("TipBot-Voucher-CURL-".$coin_name, curl_error($ch));
        die("Internal error. Please report to us. Error code 1005. Failed TX.");
    }
    curl_close ($ch);
    $data_json = json_decode($result, true);
    $transactionHash = $data_json['result']['tx_hash'];
    if (!empty($transactionHash)) {
        // 64 characters
        if(strlen($transactionHash) !== 64) return FALSE;
    } else {
        $post_to_discord = post_discord("TipBot-Voucher-CURL-".$coin_name, $result);
        return FALSE;
    }
    return $transactionHash;
}

// Function for sending Coin
function send_coin($toAddr, $amount, $coin_name) {
    global $configs;
    $ch = curl_init();
    $send_basic = '/transactions/send/basic';
    if (($coin_name == 'TRTL') || ($coin_name == 'WRKZ') || ($coin_name == 'DEGO') || ($coin_name == 'BTCMZ'))
    {
        $header = $configs['walletheader_'.strtolower($coin_name)];
        $url =  $configs['walletrpc_'.strtolower($coin_name)];
    }

    curl_setopt($ch, CURLOPT_URL, $url . $send_basic);
    curl_setopt($ch, CURLOPT_TIMEOUT, 180); //timeout in seconds
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, "{\"destination\": \"".$toAddr."\", \"amount\":".$amount."}");
    curl_setopt($ch, CURLOPT_POST, 1);

    $headers = array();
    $headers[] = "Accept: application/json";
    $headers[] = "X-API-KEY: ".$header;
    $headers[] = "Content-Type: application/x-www-form-urlencoded";
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        // echo 'Error:' . curl_error($ch);
        $post_to_discord = post_discord("TipBot-Voucher-CURL-".$coin_name, curl_error($ch));
        die("Internal error. Please report to us. Error code 1005. Failed TX.");
    }
    curl_close ($ch);

    $data_json = json_decode($result, true);
    $transactionHash = $data_json['transactionHash'];
    if (!empty($transactionHash)) {
        // 64 characters
        if(strlen($transactionHash) !== 64) return FALSE;
    } else {
        return FALSE;
    }
    return $transactionHash;
}

if (isset($_GET['sec']))
{
    $ref = $_GET['sec'];
    if (preg_match('/^[a-z0-9.\-]+$/i', $ref) == 1)
    {
        $sec = $ref;
    }
    else
    {
        header('Location: https://chat.wrkz.work/');
        exit;
    }
}
if (isset($sec)) {
    $link = new PDO("mysql:host=$dbhost;dbname=$dbname;port=$dbport", $dbusername, $dbpassword);
    $stmt = $link->prepare("SELECT * FROM cn_voucher WHERE secret_string=? LIMIT 1;");
    $stmt->execute([$sec]);
    //error case
    if(!$stmt)
    {
        die("Execute query error.");
    }
    $voucher_data = $stmt->fetch();
    if ($voucher_data['already_claimed'] == 'YES')
    {
        // Already claimed
        $errAddress = "This voucher had been claimed already.";
        $already_claimed = 'YES';
        $coin_name = $voucher_data['coin_name'];
        $coin_pref = $coin_name;
        $amount = $voucher_data['amount'] / $voucher_data['decimal'];
        $amount_str = number_format($amount, 4, '.', ',') . $voucher_data['coin_name'];
        $comment = $voucher_data['comment'];
    }
    elseif ($voucher_data == FALSE)
    {
        die("Voucher not exists!");
        exit();
    }
    else
    {
        // Not yet claimed
        $amount = $voucher_data['amount'] / $voucher_data['decimal'];
        $amount_str = number_format($amount, 4, '.', ',') . $voucher_data['coin_name'];
        $comment = $voucher_data['comment'];
        $coin_name = $voucher_data['coin_name'];
        if ($coin_name == 'TRTL')
        {
            $coin_pref = 'TRTL';
            $addr_len = 99;
            $min_addr_len = 99;
            $max_addr_len = 187;
        }  elseif ($coin_name == 'WRKZ')
        {
            $coin_pref = 'Wrkz';
            $addr_len = 98;
            $min_addr_len = 98;
            $max_addr_len = 186;
        }  elseif ($coin_name == 'DEGO')
        {
            $coin_pref = 'dg';
            $addr_len = 97;
            $min_addr_len = 97;
            $max_addr_len = 185;
        }  elseif ($coin_name == 'BTCMZ')
        {
            $coin_pref = 'btcm';
            $addr_len = 99;
            $min_addr_len = 99;
            $max_addr_len = 187;
        }  elseif ($coin_name == 'GNTL')
        {
            $coin_pref = 'gnt';
            $addr_len = 98;
            $min_addr_len = 98;
            $max_addr_len = 109;
        }   elseif ($coin_name == 'WOW')
        {
            $coin_pref = 'W';
            $addr_len = 97;
            $min_addr_len = 97;
            $max_addr_len = 108;
        }  elseif ($coin_name == 'DOGE')
        {
            $coin_pref = 'D';
            $addr_len = 34;
            $min_addr_len = 34;
            $max_addr_len = 34;
        }
    }
}
if (isset($_POST["submit"])) {
    $name = $_POST['voucher'];
    $address = $_POST['address'];
    $amount = $_POST['amount'];

    // Check if name has been entered
    if (!$_POST['voucher']) {
        // If voucher is not submitted or altered
        die("Invalid Voucher code (not set).");
        exit;
    } else {
        if (preg_match('/^[a-z0-9.\-]+$/i', $_POST['voucher']) == 1) {
            $sec = $_POST['voucher'];
        } else {
            # Invalid voucher
            die("Invalid Voucher code.");
            exit;
        }
        $link = new PDO("mysql:host=$dbhost;dbname=$dbname;port=$dbport", $dbusername, $dbpassword);
        $stmt = $link->prepare("SELECT * FROM cn_voucher WHERE secret_string=? LIMIT 1;");
        $stmt->execute([$sec]);
        //error case
        if(!$stmt) {
            die("Execute query error.");
        }
        $voucher_data = $stmt->fetch();
        if ($voucher_data['already_claimed'] == 'YES') {
            // Already claimed
            header('Location: https://chat.wrkz.work/');
            exit;
        } elseif ($voucher_data == FALSE) {
            die("Voucher not exists!");
            exit();
        } else {
            $coin_name = $voucher_data['coin_name'];
            if (strcmp($coin_name, 'TRTL') === 0) {
                $coin_pref = 'TRTL';
                $addr_len = 99;
                $min_addr_len = 99;
                $max_addr_len = 187;
                if(!startsWith($address, "TRTL")) {
                    $errAddress = "Address shall start with TRTL";
                }
            } elseif (strcmp($coin_name, 'WRKZ') === 0) {
                $coin_pref = 'Wrkz';
                $addr_len = 98;
                $min_addr_len = 98;
                $max_addr_len = 186;
                if(!startsWith($address, "Wrkz")) {
                        $errAddress = "Address shall start with Wrkz";
                }
            }  elseif (strcmp($coin_name, 'DEGO') === 0) {
                $coin_pref = 'dg';
                $addr_len = 97;
                $min_addr_len = 97;
                $max_addr_len = 185;
                if(!startsWith($address, "dg")) {
                    $errAddress = "Address shall start with dg";
                }
            }  elseif (strcmp($coin_name, 'BTCMZ') === 0) {
                $coin_pref = 'btcm';
                $addr_len = 99;
                $min_addr_len = 99;
                $max_addr_len = 187;
                if(!startsWith($address, "btcm")) {
                    $errAddress = "Address shall start with btcm";
                }
            }  elseif (strcmp($coin_name, 'GNTL') === 0) {
                $coin_pref = 'gnt';
                $addr_len = 98;
                $min_addr_len = 98;
                $max_addr_len = 109;
                if(!startsWith($address, "gnt")) {
                    $errAddress = "Address shall start with gnt";
                }
            }   elseif (strcmp($coin_name, 'WOW') === 0) {
                $coin_pref = 'W';
                $addr_len = 97;
                $min_addr_len = 97;
                $max_addr_len = 108;
                if(!startsWith($address, "Wo") && !startsWith($address, "WW") && !startsWith($address, "So")) {
                    $errAddress = "Address shall start with Wo or WW or So";
                }
            }  elseif (strcmp($coin_name, 'DOGE') === 0) {
                $coin_pref = 'D';
                $addr_len = 34;
                $min_addr_len = 34;
                $max_addr_len = 34;
                if(!startsWith($address, "D")) {
                    $errAddress = "Address shall start with D";
                }
            }

            if (strcmp($coin_name, 'DOGE') === 0) {
                $valid_address = validate_doge($address, $coin_name);
                if ($valid_address === false) {
                    $errAddress = "Invalid address for coin ".$coin_name;
                }
            } elseif (strcmp($coin_name, 'GNTL') === 0 || strcmp($coin_name, 'WOW') === 0) {
                $valid_address = validate_xmr_fam($address, $coin_name);
                if ($valid_address === false) {
                    $errAddress = "Invalid address for coin ".$coin_name;
                }
            } else {
                $valid_address = validate_address($address, $coin_name);
                if ($valid_address === false) {
                    $errAddress = "Invalid address for coin ".$coin_name;
                }
            }
            // Not yet claimed with POST
            if (!isset($errAddress)) {
                if((checkSecret_if_pending($sec)) === TRUE){
                    $result='<div class="alert alert-success">Someone is in progress of claiming this. Too late!</div>';
                } else {
                    if (strcmp($coin_name, 'DOGE') === 0) {
                        $sendPayment = send_coin_doge($address, $voucher_data['amount'], $coin_name);
                        if ($sendPayment) {
                            // Update to MySQL
                            try {
                                $updateClaim = updateStatusClaim($address, $sendPayment, $sec);
                            } catch (Exception $e) {
                                // die("Invalid link data.");
                            }
                            $result='<div class="alert alert-success">Voucher claimed, sucessfully! tx: '.$sendPayment.'</div>';
                            try {
                                $post_to_discord = post_discord("TipBot-Voucher-".$coin_name, "A user has successfully claimed ".$amount_str);
                            } catch (Exception $e) {
                            }
                        } else {
                            $result='<div class="alert alert-danger">Sorry there was an error during voucher claim. Try again later or contact us https://chat.wrkz.work</div>';
                            $post_to_discord = post_discord("TipBot-Voucher-".$coin_name, "A user has failed to claim ".$amount_str);
                        }
                    } elseif (strcmp($coin_name, 'GNTL') === 0 || strcmp($coin_name, 'WOW') === 0) {
                        $sendPayment = send_coin_xmr_fam($address, $voucher_data['amount'], $coin_name);
                        if ($sendPayment) {
                            // Update to MySQL
                            try {
                                $updateClaim = updateStatusClaim($address, $sendPayment, $sec);
                            } catch (Exception $e) {
                                // die("Invalid link data.");
                            }
                            $result='<div class="alert alert-success">Voucher claimed, sucessfully! tx: '.$sendPayment.'</div>';
                            try {
                                $post_to_discord = post_discord("TipBot-Voucher-".$coin_name, "A user has successfully claimed ".$amount_str);
                            } catch (Exception $e) {
                            }
                        } else {
                            $result='<div class="alert alert-danger">Sorry there was an error during voucher claim. Try again later or contact us https://chat.wrkz.work</div>';
                            $post_to_discord = post_discord("TipBot-Voucher-".$coin_name, "A user has failed to claim ".$amount_str);
                        }
                    } else {
                        $sendPayment = send_coin($address, $voucher_data['amount'], $coin_name);
                        if ($sendPayment) {
                            // Update to MySQL
                            try {
                                $updateClaim = updateStatusClaim($address, $sendPayment, $sec);
                            } catch (Exception $e) {
                                // die("Invalid link data.");
                            }
                            $result='<div class="alert alert-success">Voucher claimed, sucessfully! tx: '.$sendPayment.'</div>';
                            try {
                                $post_to_discord = post_discord("TipBot-Voucher-".$coin_name, "A user has successfully claimed ".$amount_str);
                            } catch (Exception $e) {
                            }
                        } else {
                            $result='<div class="alert alert-danger">Sorry there was an error during voucher claim. Try again later or contact us https://chat.wrkz.work</div>';
                            $post_to_discord = post_discord("TipBot-Voucher-".$coin_name, "A user has failed to claim ".$amount_str);
                        }
                    }
                }
            }
        }
    }
}
?>

<?php
    $actual_link = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? "https" : "http") . "://$_SERVER[HTTP_HOST]$_SERVER[REQUEST_URI]";
	$image_png = $voucher_data['voucher_image_name'];
?>
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Get Voucher From https://chat.wrkz.work">
    <meta name="author" content="WrkzCoin Community Team">
    <meta property="og:type" content="website">
    <meta property="og:url" content="<?php echo $actual_link;?>">
    <meta property="og:title" content="Share Digital Voucher via TipBot">
    <meta property="og:description" content="Tip and share crypto voucher with Discord, Telegram TipBot">
    <meta property="og:image" content="https://redeem.bot.tips/tipbot_voucher/<?php echo $image_png;?>">
    <meta name="twitter:card" content="summary_large_image">
    <title>Claim Crypto Voucher Powered by Bot.Tips and WrkzCoin</title>
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap.min.css">
  </head>
  <body>
      <div class="container">
          <div class="row">
              <div class="col-md-8 col-md-offset-2">
                  <h1 class="page-header text-center">Claim Voucher <?php echo $coin_name; ?></h1>
                  <div class="text-center">
                      <img src="https://redeem.bot.tips/tipbot_voucher/<?php echo $image_png;?>" style="height: 250px;" class="rounded" alt="Scan with QR">
                  </div>
                  <h3 class="text-center"></h3>
                <form class="form-horizontal" role="form" method="post" action="<?php echo $_SERVER['REQUEST_URI']; ?>">
                    <div class="form-group">
                        <label for="name" class="col-sm-2 control-label">Voucher Code:</label>
                        <div class="col-sm-10">
                            <input type="text" class="form-control" id="voucher" name="voucher" placeholder="Voucher Code" value="<?php echo $sec; ?>" readonly>
                            <?php if (isset($errVoucher)) { echo "<p class='text-danger'>$errVoucher</p>"; }?>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="name" class="col-sm-2 control-label">Claimed to:</label>
                        <div class="col-sm-10">
                            <input type="text" class="form-control" id="address" name="address" placeholder="<?php echo $coin_pref;?>" value="<?php if (isset($_POST['address'])) { echo htmlspecialchars($_POST['address']); } ?>" minlength="<?php echo $min_addr_len;?>" maxlength="<?php echo $max_addr_len;?>" required="required">
                            <?php if (isset($errAddress)) { echo "<p class='text-danger'>$errAddress</p>"; } ?>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="amount" class="col-sm-2 control-label">Amount</label>
                        <div class="col-sm-10">
                            <input type="text" class="form-control" id="amount" name="amount" placeholder="1000.000" value="<?php echo $amount_str; ?>" readonly>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="message" class="col-sm-2 control-label">Message</label>
                        <div class="col-sm-10">
                            <textarea class="form-control" rows="4" name="message" readonly><?php echo $comment;?></textarea>
                        </div>
                    </div>

                    <div class="form-group">
                        <div class="col-sm-10 col-sm-offset-2">
                            <input id="submit" name="submit" type="submit" value="Claim Now!" class="btn btn-primary" <?php if (isset($already_claimed)) {echo "disabled"; }?> >
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="col-sm-10 col-sm-offset-2">
                            <?php if (isset($result)) { echo $result;} ?>    
                        </div>
                    </div>
                </form> 
            </div>
        </div>
<!-- Include Font Awesome Stylesheet in Header -->
<link href="//cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css" rel="stylesheet">
<!-- // -->
        <div class="row">
            <div class="text-center center-block">
               <a href="https://chat.wrkz.work" target="_blank"><i class="fa fa-wechat -square fa-3x social"></i></a>
               <a href="https://t.me/wrkzcoinchat" target="_blank"><i class="fa fa-telegram -square fa-3x social"></i></a> 
               <a href="https://twitter.com/wrkzdev" target="_blank"><i class="fa fa-twitter-square fa-3x social"></i></a>
               <a href="https://github.com/wrkzcoin/TipBot" target="_blank"><i class="fa fa-github-square fa-3x social"></i></a>
        </div>
    <hr>
        </div>

<style>
.social:hover {
     -webkit-transform: scale(1.1);
     -moz-transform: scale(1.1);
     -o-transform: scale(1.1);
 }
 .social {
     -webkit-transform: scale(0.8);
     /* Browser Variations: */
     
     -moz-transform: scale(0.8);
     -o-transform: scale(0.8);
     -webkit-transition-duration: 0.5s;
     -moz-transition-duration: 0.5s;
     -o-transition-duration: 0.5s;
 }

/*
    Multicoloured Hover Variations
*/
 
 #social-fb:hover {
     color: #3B5998;
 }
 #social-tw:hover {
     color: #4099FF;
 }
 #social-gp:hover {
     color: #d34836;
 }
 #social-em:hover {
     color: #f39c12;
 }
</style>
    </div>
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/js/bootstrap.min.js"></script>
  </body>
</html>

