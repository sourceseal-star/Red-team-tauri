import * as LocalAuthentication from 'expo-local-authentication';

/**
 * Checks if biometric hardware is available and if the user has enrolled biometrics.
 * @returns A promise resolving to true if biometric authentication can be used.
 */
export async function isBiometricAvailable(): Promise<boolean> {
  try {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    const isEnrolled = await LocalAuthentication.isEnrolledAsync();
    return hasHardware && isEnrolled;
  } catch (error) {
    console.error('Error checking biometric availability:', error);
    return false;
  }
}

/**
 * Initiates biometric authentication.
 * @param reason The message showing why biometric authentication is requested.
 * @returns A promise resolving to true if authentication succeeded.
 */
export async function authenticateBiometric(reason: string): Promise<boolean> {
  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: reason,
      fallbackLabel: 'Usar contraseña',
      disableDeviceFallback: false,
    });
    return result.success;
  } catch (error) {
    console.error('Error during biometric authentication:', error);
    return false;
  }
}
