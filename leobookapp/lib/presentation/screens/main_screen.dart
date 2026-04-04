// main_screen.dart: main_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: MainScreen, _MainScreenState

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/presentation/screens/home_screen.dart';
import 'package:leobookapp/presentation/screens/account_screen.dart';
import 'package:leobookapp/presentation/screens/rule_engine/backtest_dashboard.dart';
import 'package:leobookapp/presentation/screens/top_predictions_screen.dart';
import 'package:leobookapp/presentation/widgets/shared/main_top_bar.dart';
import 'package:leobookapp/presentation/widgets/shared/tier_gate.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/data/models/match_model.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;
  bool _showProfilePanel = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return LayoutBuilder(
      builder: (context, constraints) {
        final isDesktop = constraints.maxWidth > 1024;

        return BlocBuilder<HomeCubit, HomeState>(
          builder: (context, state) {
            Widget bodyArea;

            if (state is HomeLoaded) {
              final mainTabs = [
                    HomeScreen(
                      onViewAllPredictions: () =>
                          setState(() => _currentIndex = 2),
                    ),
                    const TierGate(
                      requirement: TierRequirement.canAutomateBetting,
                      featureName: 'Rule Engine & Backtesting',
                      featureDescription:
                          'Build custom rules, run backtests, and automate betting. Pro only.',
                      child: BacktestDashboard(),
                    ),
                    const TopPredictionsScreen(),
                    if (!isDesktop) const AccountScreen(),
                  ];

              final content = Column(
                children: [
                  MainTopBar(
                    currentIndex: _currentIndex,
                    onTabChanged: (i) => setState(() {
                      _currentIndex = i.clamp(0, mainTabs.length - 1);
                      if (isDesktop) _showProfilePanel = false;
                    }),
                    onProfileTap: isDesktop ? () => setState(() => _showProfilePanel = !_showProfilePanel) : null,
                  ),
                  Expanded(
                    child: Row(
                      children: [
                        Expanded(
                          child: IndexedStack(
                            index: _currentIndex.clamp(0, mainTabs.length - 1),
                            children: mainTabs,
                          ),
                        ),
                        // Desktop right-side profile panel
                        if (isDesktop)
                          AnimatedContainer(
                            duration: const Duration(milliseconds: 250),
                            curve: Curves.easeOutCubic,
                            width: _showProfilePanel ? 380 : 0,
                            child: _showProfilePanel
                                ? Container(
                                    decoration: BoxDecoration(
                                      color: AppColors.neutral900,
                                      border: Border(
                                        left: BorderSide(
                                          color: Colors.white.withValues(alpha: 0.06),
                                        ),
                                      ),
                                    ),
                                    child: const ClipRect(
                                      child: AccountScreen(),
                                    ),
                                  )
                                : const SizedBox.shrink(),
                          ),
                      ],
                    ),
                  ),
                ],
              );

              bodyArea = BlocProvider<SearchCubit>(
                create: (context) => SearchCubit(
                  allMatches: state.allMatches.cast<MatchModel>(),
                  allRecommendations: state.filteredRecommendations,
                ),
                child: content,
              );
            } else {
              bodyArea = Column(
                children: [
                  MainTopBar(
                    currentIndex: _currentIndex,
                    onTabChanged: (i) => setState(() => _currentIndex = i),
                    onProfileTap: isDesktop ? () => setState(() => _showProfilePanel = !_showProfilePanel) : null,
                  ),
                  Expanded(
                    child: IndexedStack(
                      index: _currentIndex,
                      children: [
                        HomeScreen(
                          onViewAllPredictions: () =>
                              setState(() => _currentIndex = 2),
                        ),
                        const BacktestDashboard(),
                        const TopPredictionsScreen(),
                        if (!isDesktop) const AccountScreen(),
                      ],
                    ),
                  ),
                ],
              );
            }

            return Scaffold(
              extendBody: true,
              body: bodyArea,
              bottomNavigationBar:
                  isDesktop ? null : _buildFloatingNavBar(isDark),
            );
          },
        );
      },
    );
  }

  Widget _buildFloatingNavBar(bool isDark) {
    return Container(
      height: Responsive.sp(context, 56),
      margin: EdgeInsets.fromLTRB(
        Responsive.sp(context, 16),
        0,
        Responsive.sp(context, 16),
        Responsive.sp(context, 24),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Responsive.sp(context, 28)),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
          child: Container(
            decoration: BoxDecoration(
              color: isDark
                  ? AppColors.neutral800.withValues(alpha: 0.95)
                  : Colors.white.withValues(alpha: 0.92),
              borderRadius: BorderRadius.circular(Responsive.sp(context, 28)),
              border: Border.all(
                color: isDark
                    ? AppColors.primary.withValues(alpha: 0.12)
                    : Colors.black.withValues(alpha: 0.06),
                width: 0.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.25),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildNavItem(0, Icons.home_rounded, "HOME"),
                _buildNavItem(1, Icons.auto_graph_rounded, "RULES"),
                _buildNavItem(2, Icons.emoji_events_rounded, "TOP"),
                _buildNavItem(3, Icons.person_rounded, "PROFILE"),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(int index, IconData icon, String label) {
    final isSelected = _currentIndex == index;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GestureDetector(
      onTap: () {
        setState(() => _currentIndex = index);
        HapticFeedback.lightImpact();
      },
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: Responsive.sp(context, 12)),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeOutCubic,
              padding: EdgeInsets.symmetric(
                horizontal: Responsive.sp(context, 14),
                vertical: Responsive.sp(context, 5),
              ),
              decoration: BoxDecoration(
                gradient: isSelected
                    ? LinearGradient(
                        colors: [
                          AppColors.primary.withValues(alpha: 0.25),
                          AppColors.primary.withValues(alpha: 0.10),
                        ],
                      )
                    : null,
                color: isSelected ? null : Colors.transparent,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(
                icon,
                size: Responsive.sp(context, 18),
                color: isSelected
                    ? AppColors.primary
                    : (isDark ? Colors.white38 : Colors.black38),
              ),
            ),
            SizedBox(height: Responsive.sp(context, 2)),
            Text(
              label,
              style: TextStyle(
                fontFamily: 'DM Sans',
                fontSize: Responsive.sp(context, 6),
                fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                color: isSelected
                    ? AppColors.primary
                    : (isDark ? Colors.white24 : Colors.black26),
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
