export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  objective: string;
  difficulty: string;
  is_active: boolean;
}

export interface Workout {
  id: number;
  name: string;
  day: string;
  exercises: Exercise[];
}

export interface Exercise {
  id: number;
  name: string;
  sets: number;
  reps: number;
  weight?: number;
}

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  client: Client | null;
  isLoading: boolean;
  error: string | null;
}