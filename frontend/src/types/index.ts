export interface Provider {
  id: string;
  name: string;
  specialization: string | null;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface Client {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface Appointment {
  id: string;
  client_id: string;
  provider_id: string;
  room_id: string | null;
  start_time: string;
  end_time: string;
  appointment_type: string | null;
  priority: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AppointmentWithClient extends Appointment {
  client?: Client;
}
