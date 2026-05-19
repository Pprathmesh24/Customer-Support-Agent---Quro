import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

const PROTECTED_PREFIXES = ['/chat', '/admin'];
const AUTH_PREFIXES = ['/login', '/signup'];

export async function middleware(request: NextRequest): Promise<NextResponse> {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // getUser() validates the token server-side on every request.
  // Never use getSession() here — it trusts the client cookie without verification.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(p => pathname.startsWith(p));
  const isAuthRoute = AUTH_PREFIXES.some(p => pathname.startsWith(p));

  if (!user && isProtected) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    return NextResponse.redirect(url);
  }

  if (user && isAuthRoute) {
    const url = request.nextUrl.clone();
    url.pathname = '/chat';
    return NextResponse.redirect(url);
  }

  // Root path: redirect based on auth state.
  if (pathname === '/') {
    const url = request.nextUrl.clone();
    url.pathname = user ? '/chat' : '/login';
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: [
    // Run on all paths except Next.js internals and static assets.
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
