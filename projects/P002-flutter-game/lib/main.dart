import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'game/game_state.dart';
import 'screens/hub_screen.dart';
import 'services/audio_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

  runApp(const OctoBattleApp());
}

class OctoBattleApp extends StatelessWidget {
  const OctoBattleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => GameStateNotifier()..initialize()),
        Provider<AudioService>(create: (_) => AudioService()),
      ],
      child: MaterialApp(
        title: '封印の戦線',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF1A0A2E),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          textTheme: GoogleFonts.dotGothic16TextTheme(
            ThemeData.dark().textTheme,
          ),
          scaffoldBackgroundColor: const Color(0xFF0D0D1A),
        ),
        home: const HubScreen(),
      ),
    );
  }
}
