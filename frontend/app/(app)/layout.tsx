import { Sidebar } from "@/components/Sidebar";
import { getMyPageAccess } from "@/lib/api";

export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const allowedPages = await getMyPageAccess();

  return (
    <div className="flex min-h-screen">
      <Sidebar allowedPages={allowedPages} />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
