// user_state.dart: Auth states for UserCubit.
// Part of LeoBook App — State Management (Cubit)
//
// Classes: UserState, UserInitial, UserLoading, UserAuthenticated, UserError

part of 'user_cubit.dart';

abstract class UserState extends Equatable {
  final UserModel user;
  const UserState({required this.user});

  @override
  List<Object?> get props => [user];
}

/// Initial / guest state (not authenticated)
class UserInitial extends UserState {
  const UserInitial({required super.user});
}

/// Loading during auth operations
class UserLoading extends UserState {
  const UserLoading({required super.user});
}

/// Successfully authenticated
class UserAuthenticated extends UserState {
  const UserAuthenticated({required super.user});
}

/// Auth error occurred
class UserError extends UserState {
  final String message;
  const UserError({required super.user, required this.message});

  @override
  List<Object?> get props => [user, message];
}
