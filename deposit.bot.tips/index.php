<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Turn off all error reporting
//error_reporting(0);

$configs = include('config.php');

$dbhost = $configs['mysql_host'];
$dbname = $configs['mysql_dbname'];
$dbusername = $configs['mysql_user'];
$dbpassword = $configs['mysql_password'];
$deposit_url = "https://deposit.bot.tips";

if (isset($_GET['key']))
{
    $ref = $_GET['key'];
    if (preg_match('/^[a-z0-9.\-]+$/i', $ref) == 1)
    {
        $key = $ref;
    }
    else
    {
        header('Location: https://chat.wrkz.work/');
        exit;
    }
}

if (isset($key)) {
    $link = new PDO("mysql:host=$dbhost;dbname=$dbname", $dbusername, $dbpassword);
    $stmt = $link->prepare("SELECT * FROM discord_depositlink WHERE link_key=? LIMIT 1;");
    $stmt->execute([$key]);
    //error case
    if(!$stmt)
    {
        die("Execute query error.");
    }
    $user_data = $stmt->fetch();
    if ($user_data['enable'] == 'YES')
    {
        $stmt = $link->prepare("SELECT * FROM discord_depositlink_address WHERE user_id=?;");
        $stmt->execute([$user_data['user_id']]);
        if(!$stmt)
        {
            die("Execute query error.");
        }
        $user_coin_list = $stmt->fetchAll();
        if (count($user_coin_list) == 0) {
            die("No list of coins! Try again later.");
        }
    } elseif ($user_data['enable'] == 'NO') {
        die("Deposit link not enable!");
    } elseif ($user_data == FALSE)
    {
        die("Deposit link not exists!");
        exit();
    }
}
$actual_link = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? "https" : "http") . "://$_SERVER[HTTP_HOST]$_SERVER[REQUEST_URI]";

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
    <meta property="og:title" content="Deposit with Crypto TipBot and Start to tip people with Crypto">
    <meta property="og:description" content="Tip and share crypto with Discord, Telegram TipBot">
    <meta property="og:image" content="https://deposit.bot.tips/image_card.png">
    <meta name="twitter:card" content="summary_large_image">
    <title>Deposit to Discord TipBot Powered by Bot.Tips and WrkzCoin</title>

    <!-- Include Font Awesome Stylesheet in Header -->
    <link href="//cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css" rel="stylesheet">
    <link href="//maxcdn.bootstrapcdn.com/bootstrap/4.1.1/css/bootstrap.min.css" rel="stylesheet" id="bootstrap-css">
    <script src="//maxcdn.bootstrapcdn.com/bootstrap/4.1.1/js/bootstrap.min.js"></script>
    <script src="//cdnjs.cloudflare.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>
    <!------ Include the above in your HEAD tag ---------->
    <link rel="stylesheet" type="text/css" href="//deposit.bot.tips/card.css">

  </head>
  <body>
  


<!-- Team -->
<section id="team" class="pb-5">
    <div class="container">
        <h5 class="section-title h1">DEPOSIT WALLET ADDRESSES WITH TIPBOT</h5>
        <div class="row">
            <?php
			foreach ($user_coin_list as $each_coin) {
            ?>
            <!-- Team member -->
            <div class="col-xs-12 col-sm-6 col-md-3">
                <div class="image-flip" ontouchstart="this.classList.toggle('hover');">
                    <div class="mainflip">
                        <div class="backside">
                            <div class="card" style="width: 16rem;">
                                <div class="card-body text-center mt-4">
                                    <h4 class="card-title"><?php echo $each_coin['coin_name'];?></h4>
                                    <p class="card-text"><?php echo $each_coin['deposit_address'];?></p>
                                    <ul class="list-inline">
                                        <li class="list-inline-item">
                                            <a class="social-icon text-xs-center" target="_blank" href="https://twitter.com/wrkzdev">
                                                <i class="fa fa-twitter"></i>
                                            </a>
                                        </li>
                                        <li class="list-inline-item">
                                            <a class="social-icon text-xs-center" target="_blank" href="https://chat.wrkz.work">
                                                <i class="fa fa-wechat"></i>
                                            </a>
                                        </li>
                                        <li class="list-inline-item">
                                            <a class="social-icon text-xs-center" target="_blank" href="https://t.me/wrkzcoinchat">
                                                <i class="fa fa-telegram"></i>
                                            </a>
                                        </li>
                                        <li class="list-inline-item">
                                            <a class="social-icon text-xs-center" target="_blank" href="https://github.com/wrkzcoin/TipBot">
                                                <i class="fa fa-github"></i>
                                            </a>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                        <div class="frontside">
                            <div class="card">
                                <div class="card-body text-center mt-4">
                                    <h5 class="card-title"><?php echo $each_coin['coin_name'];?></h5>
                                    <p class="card-text"><img src="<?php echo $deposit_url . "/tipbot_deposit_qr/" . $each_coin['deposit_address'] . ".png"; ?>" style="height: 200px;" alt="card image"></p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <!-- ./Team member -->
        <?php
			}
        ?>
        </div>
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
    </div>
</section>
<!-- Team -->

  </body>
</html>