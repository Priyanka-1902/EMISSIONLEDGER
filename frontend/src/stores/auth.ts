import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Amplify } from 'aws-amplify'
import {
  signIn, signOut, getCurrentUser, fetchAuthSession,
  fetchUserAttributes,
} from 'aws-amplify/auth'

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
      loginWith: {
        oauth: {
          domain: import.meta.env.VITE_COGNITO_DOMAIN,
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: [window.location.origin + '/'],
          redirectSignOut: [window.location.origin + '/login'],
          responseType: 'code',
        }
      }
    }
  }
})

interface AuthState {
  user: { id: string; email: string; name: string; role: string } | null
  token: string | null
  tenant: { id: string; slug: string; name: string; tier: string } | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
  loadSession: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      tenant: null,

      login: async (email: string, password: string) => {
        await signIn({ username: email, password })
        await get().loadSession()
      },

      logout: async () => {
        await signOut()
        set({ user: null, token: null, tenant: null })
      },

      refreshToken: async () => {
        const session = await fetchAuthSession({ forceRefresh: true })
        const token = session.tokens?.idToken?.toString() ?? null
        set({ token })
      },

      loadSession: async () => {
        try {
          const session = await fetchAuthSession()
          const token = session.tokens?.idToken?.toString() ?? null
          const attrs = await fetchUserAttributes()
          if (token && attrs) {
            set({
              token,
              user: {
                id: attrs.sub ?? '',
                email: attrs.email ?? '',
                name: attrs.name ?? '',
                role: attrs['custom:role'] ?? 'plant_manager',
              },
              tenant: {
                id: attrs['custom:tenant_id'] ?? '',
                slug: attrs['custom:tenant_slug'] ?? '',
                name: attrs['custom:tenant_name'] ?? '',
                tier: attrs['custom:tenant_tier'] ?? 'entry',
              },
            })
          }
        } catch {
          set({ user: null, token: null })
        }
      },
    }),
    {
      name: 'el-auth',
      partialize: state => ({ user: state.user, tenant: state.tenant }),
    }
  )
)
