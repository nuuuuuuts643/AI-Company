import 'package:flutter/material.dart';

/// 広告サービス
/// - 無料版: ステージクリア後にインタースティシャル広告を表示
/// - 有料版($2.99): [isAdFree] = true にして広告を完全除去
///
/// 実際の広告実装: google_mobile_ads パッケージを pubspec.yaml に追加して
/// 以下のコメントアウト部分を有効化する。
class AdService {
  AdService._();

  static final AdService instance = AdService._();

  /// 有料版フラグ
  /// true = 広告なし（$2.99 アンロック済み）
  bool _isAdFree = false;
  bool get isAdFree => _isAdFree;

  // ---- 広告ID (本番用に差し替える) ----
  static const String _interstitialAdUnitIdIOS =
      'ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX'; // 本番ID
  static const String _testInterstitialId =
      'ca-app-pub-3940256099942544/4411468910'; // GoogleテストID

  /// 初期化（アプリ起動時 / セーブデータロード後に呼ぶ）
  Future<void> initialize({required bool isAdFree}) async {
    _isAdFree = isAdFree;
    if (!_isAdFree) {
      // google_mobile_ads 実装時:
      // await MobileAds.instance.initialize();
      // _preloadInterstitial();
      debugPrint('[AdService] Initialized — ad mode');
    } else {
      debugPrint('[AdService] Initialized — ad-free mode');
    }
  }

  /// 有料版アンロック（決済完了後に呼ぶ）
  /// in_app_purchase パッケージで $2.99 非消費型購入を実装する。
  Future<bool> purchaseAdFree() async {
    // 実装例:
    // final purchaseParam = PurchaseParam(productDetails: ...);
    // InAppPurchase.instance.buyNonConsumable(purchaseParam: purchaseParam);
    _isAdFree = true;
    debugPrint('[AdService] Ad-free version unlocked');
    return true;
  }

  /// インタースティシャル広告を表示
  /// クリア後に呼ぶ。[onClosed] は広告閉幕後に実行される。
  Future<void> showInterstitial({required VoidCallback onClosed}) async {
    if (_isAdFree) {
      onClosed();
      return;
    }
    // google_mobile_ads 実装例:
    // InterstitialAd.load(
    //   adUnitId: kDebugMode ? _testInterstitialId : _interstitialAdUnitIdIOS,
    //   request: const AdRequest(),
    //   adLoadCallback: InterstitialAdLoadCallback(
    //     onAdLoaded: (ad) {
    //       ad.fullScreenContentCallback = FullScreenContentCallback(
    //         onAdDismissedFullScreenContent: (_) {
    //           ad.dispose();
    //           onClosed();
    //         },
    //       );
    //       ad.show();
    //     },
    //     onAdFailedToLoad: (_) => onClosed(),
    //   ),
    // );

    // プレースホルダー（SDKなし）
    debugPrint('[AdService] Interstitial ad placeholder');
    onClosed();
  }

  /// バナー広告ウィジェット（リザルト画面下部など）
  /// 有料版では空ウィジェットを返す。
  static Widget banner() {
    if (instance._isAdFree) return const SizedBox.shrink();
    // google_mobile_ads 実装時: return AdWidget(ad: _bannerAd);
    return Container(
      height: 50,
      color: const Color(0xFF2E2E2E),
      child: Center(
        child: Text(
          '広告スペース（Google Mobile Ads）',
          style: TextStyle(
            color: Colors.white.withOpacity(0.4),
            fontSize: 11,
            fontFamily: 'DotGothic16',
          ),
        ),
      ),
    );
  }
}
