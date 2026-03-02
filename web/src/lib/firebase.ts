import { initializeApp, getApps, getApp, FirebaseApp } from "firebase/app";
import {
  getAuth,
  connectAuthEmulator,
  Auth,
  browserLocalPersistence,
  setPersistence,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

function getFirebaseApp(): FirebaseApp {
  if (getApps().length > 0) {
    return getApp();
  }
  return initializeApp(firebaseConfig);
}

let authInstance: Auth | null = null;

export function getFirebaseAuth(): Auth {
  if (authInstance) {
    return authInstance;
  }

  const app = getFirebaseApp();
  const auth = getAuth(app);

  setPersistence(auth, browserLocalPersistence).catch(() => {
    // Persistence setup is best-effort; silently ignore errors.
  });

  if (
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR === "true" &&
    typeof window !== "undefined"
  ) {
    connectAuthEmulator(auth, "http://localhost:9099", { disableWarnings: true });
  }

  authInstance = auth;
  return auth;
}

// Exported for testing — allows resetting the singleton between tests.
export function resetAuthInstance(): void {
  authInstance = null;
}
