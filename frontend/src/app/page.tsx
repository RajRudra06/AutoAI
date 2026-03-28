import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function Home() {
  const session = await auth();

  if (!session.userId) {
    redirect("/sign-in");
  }

  redirect("/welcome");
}
