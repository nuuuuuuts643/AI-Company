import 'package:flutter/material.dart';

/// 全画面共通の画面遷移アニメーション
class AppTransitions {
  AppTransitions._();

  // フェードトランジション（メニュー間）
  static PageRouteBuilder<T> fade<T>(Widget page,
      {Duration duration = const Duration(milliseconds: 350)}) {
    return PageRouteBuilder<T>(
      pageBuilder: (_, __, ___) => page,
      transitionDuration: duration,
      reverseTransitionDuration: duration,
      transitionsBuilder: (_, animation, __, child) {
        return FadeTransition(
          opacity: CurvedAnimation(parent: animation, curve: Curves.easeInOut),
          child: child,
        );
      },
    );
  }

  // スライドアップ（バトル開始時）
  static PageRouteBuilder<T> slideUp<T>(Widget page,
      {Duration duration = const Duration(milliseconds: 480)}) {
    return PageRouteBuilder<T>(
      pageBuilder: (_, __, ___) => page,
      transitionDuration: duration,
      reverseTransitionDuration: const Duration(milliseconds: 320),
      transitionsBuilder: (_, animation, secondaryAnimation, child) {
        final slide = Tween<Offset>(
          begin: const Offset(0, 1.0),
          end: Offset.zero,
        ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOutCubic));
        final fade = CurvedAnimation(parent: animation, curve: Curves.easeIn);
        return SlideTransition(
          position: slide,
          child: FadeTransition(opacity: fade, child: child),
        );
      },
    );
  }

  // スライドダウン（バトル終了・リザルト）
  static PageRouteBuilder<T> slideDown<T>(Widget page,
      {Duration duration = const Duration(milliseconds: 500)}) {
    return PageRouteBuilder<T>(
      pageBuilder: (_, __, ___) => page,
      transitionDuration: duration,
      reverseTransitionDuration: const Duration(milliseconds: 350),
      transitionsBuilder: (_, animation, secondaryAnimation, child) {
        final slide = Tween<Offset>(
          begin: const Offset(0, -0.12),
          end: Offset.zero,
        ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOutQuart));
        final fade = CurvedAnimation(parent: animation, curve: Curves.easeIn);
        return SlideTransition(
          position: slide,
          child: FadeTransition(opacity: fade, child: child),
        );
      },
    );
  }

  // スケール＋フェード（リザルト画面など劇的な登場）
  static PageRouteBuilder<T> scaleReveal<T>(Widget page,
      {Duration duration = const Duration(milliseconds: 600)}) {
    return PageRouteBuilder<T>(
      pageBuilder: (_, __, ___) => page,
      transitionDuration: duration,
      reverseTransitionDuration: const Duration(milliseconds: 300),
      transitionsBuilder: (_, animation, __, child) {
        final scale = Tween<double>(begin: 0.88, end: 1.0).animate(
          CurvedAnimation(parent: animation, curve: Curves.easeOutBack),
        );
        final fade = CurvedAnimation(parent: animation, curve: Curves.easeIn);
        return ScaleTransition(
          scale: scale,
          child: FadeTransition(opacity: fade, child: child),
        );
      },
    );
  }

  // 横スライド（ステージ選択→装備など横移動）
  static PageRouteBuilder<T> slideRight<T>(Widget page,
      {Duration duration = const Duration(milliseconds: 380)}) {
    return PageRouteBuilder<T>(
      pageBuilder: (_, __, ___) => page,
      transitionDuration: duration,
      reverseTransitionDuration: duration,
      transitionsBuilder: (_, animation, __, child) {
        final slide = Tween<Offset>(
          begin: const Offset(1.0, 0),
          end: Offset.zero,
        ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOutCubic));
        return SlideTransition(position: slide, child: child);
      },
    );
  }
}
