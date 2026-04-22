import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'game/game_state.dart';
import 'screens/main_menu_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ポートレート固定（iPhone縦向き）
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // 全画面表示（ステータスバー非表示）
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

  runApp(const OctoBattleApp());
}

class OctoBattleApp extends StatelessWidget {
  const OctoBattleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => GameStateNotifier()..initialize(),
      child: MaterialApp(
        title: '封印の戦線',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF1A0A2E),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          fontFamily: 'DotGothic16',
          scaffoldBackgroundColor: const Color(0xFF0D0D1A),
        ),
        home: const MainMenuScreen(),
      ),
    );
  }
}
