// main.dart: main.dart: Widget/screen for Unknown.
// Part of LeoBook Unknown
//
// Classes: LeoBookApp

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:leobookapp/core/theme/app_theme_v2.dart';
import 'package:leobookapp/core/theme/theme_cubit.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/data/repositories/news_repository.dart';
import 'package:leobookapp/presentation/screens/splash_screen.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';
import 'package:leobookapp/data/repositories/auth_repository.dart';
import 'package:leobookapp/core/services/update_service.dart';

import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:leobookapp/core/config/supabase_config.dart';

import 'package:leobookapp/core/services/secure_storage.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load environment variables
  await dotenv.load(fileName: ".env");

  await Supabase.initialize(
    url: SupabaseConfig.supabaseUrl,
    anonKey: SupabaseConfig.supabaseAnonKey,
    authOptions: FlutterAuthClientOptions(
      localStorage: SecureSupabaseStorage(),
    ),
  );

  // google_sign_in v7: initialize the singleton ONCE before runApp.
  // Without this, authenticate() hangs indefinitely on mobile.
  // serverClientId MUST be the Web OAuth 2.0 client ID (not Android/iOS).
  if (!kIsWeb) {
    await GoogleSignIn.instance.initialize(
      serverClientId: dotenv.env['GOOGLE_WEB_CLIENT_ID'],
    );
  }

  runApp(const LeoBookApp());
}

class LeoBookApp extends StatelessWidget {
  const LeoBookApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider(create: (context) => AuthRepository()),
        RepositoryProvider(create: (context) => DataRepository()),
        RepositoryProvider(create: (context) => NewsRepository()),
      ],
      child: MultiBlocProvider(
          providers: [
            BlocProvider<HomeCubit>(
              create: (context) => HomeCubit(
                context.read<DataRepository>(),
                context.read<NewsRepository>(),
              )..loadDashboard(),
            ),
            BlocProvider<UserCubit>(create: (context) => UserCubit(context.read<AuthRepository>())),
            BlocProvider<ThemeCubit>(create: (_) => ThemeCubit()),
            BlocProvider<UpdateCubit>(
              create: (_) => UpdateCubit()..startPeriodicCheck(intervalSeconds: 3),
            ),
          ],
          child: BlocBuilder<ThemeCubit, ThemeMode>(
            builder: (context, themeMode) => MaterialApp(
              title: 'LeoBook',
              theme: AppThemeV2.lightTheme,
              darkTheme: AppThemeV2.darkTheme,
              themeMode: themeMode,
              home: const SplashScreen(),
              debugShowCheckedModeBanner: false,
              builder: (context, child) {
                const double scale = 1;
                final mq = MediaQuery.of(context);
                return Transform.scale(
                  scale: scale,
                  alignment: Alignment.topLeft,
                  child: SizedBox(
                    width: mq.size.width / scale,
                    height: mq.size.height / scale,
                    child: MediaQuery(
                      data: mq.copyWith(
                        size: Size(
                          mq.size.width / scale,
                          mq.size.height / scale,
                        ),
                      ),
                      child: child!,
                    ),
                  ),
                );
              },
            ),
          ),
      ),
    );
  }
}
