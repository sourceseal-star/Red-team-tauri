import * as SecureStore from 'expo-secure-store';

/**
 * Saves a key-value pair securely in the device's secure storage.
 * @param key The identifier key.
 * @param value The sensitive value to store (token, API key, etc.).
 */
export async function saveSecure(key: string, value: string): Promise<void> {
  await SecureStore.setItemAsync(key, value);
}

/**
 * Loads a value securely from the device's secure storage.
 * @param key The identifier key.
 */
export async function loadSecure(key: string): Promise<string | null> {
  return await SecureStore.getItemAsync(key);
}

/**
 * Deletes a securely stored key-value pair.
 * @param key The identifier key.
 */
export async function deleteSecure(key: string): Promise<void> {
  await SecureStore.deleteItemAsync(key);
}
