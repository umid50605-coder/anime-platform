// Mirrors ResetPasswordRequest.new_password in backend/app/schemas/auth.py.
// The server is the authority; these exist so the form can say so before a round trip.
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 128;
