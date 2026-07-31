export const secureStorage = {
  getItem: async (key: string): Promise<string | null> => {
    return new Promise((resolve) => {
      // Mock retrieve
      resolve(null);
    });
  },
  setItem: async (key: string, value: string): Promise<void> => {
    return new Promise((resolve) => {
      // Mock store
      resolve();
    });
  },
  removeItem: async (key: string): Promise<void> => {
    return new Promise((resolve) => {
      resolve();
    });
  },
};
