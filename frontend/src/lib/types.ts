export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string | null;
  is_active: boolean;
  is_staff: boolean;
  date_joined: string;
  permissions: string[];
}

export interface Role {
  code: string;
  name: string;
  description: string;
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
  details?: unknown;
}
