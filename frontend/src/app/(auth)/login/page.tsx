import { LoginForm } from "./login-form";

export const metadata = { title: "Log in · CASIO" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next, reset, deleted } = await searchParams;
  return <LoginForm next={typeof next === "string" ? next : undefined} justReset={reset === "1"} justDeleted={deleted === "1"} />;
}
