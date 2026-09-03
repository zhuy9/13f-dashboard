import { initializeApp } from 'firebase/app'
import { getFirestore } from 'firebase/firestore'

const apiKey = import.meta.env.VITE_FIREBASE_API_KEY
const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID
const appId = import.meta.env.VITE_FIREBASE_APP_ID

if (!apiKey || !projectId || !appId) {
  throw new Error(
    'Missing Firebase config. Copy web/.env.example to web/.env and fill in VITE_FIREBASE_API_KEY, VITE_FIREBASE_PROJECT_ID, and VITE_FIREBASE_APP_ID.',
  )
}

const app = initializeApp({
  apiKey,
  authDomain: `${projectId}.firebaseapp.com`,
  projectId,
  appId,
})

export const db = getFirestore(app)
