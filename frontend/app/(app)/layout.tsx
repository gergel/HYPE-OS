import { ConfirmProvider } from "@/components/ConfirmProvider";
import { NavigationTracker } from "@/components/NavigationTracker";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/ToastProvider";
import { getMyPageAccess } from "@/lib/api";
import { LiveProvider } from "@/lib/live";

export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const allowedPages = await getMyPageAccess();

  return (
    <ToastProvider>
      <ConfirmProvider>
        <LiveProvider>
          <div className="flex min-h-screen">
            <NavigationTracker />
            <Sidebar allowedPages={allowedPages} />
            <main className="flex min-w-0 flex-1 flex-col">{children}</main>
          </div>
        </LiveProvider>
      </ConfirmProvider>
    </ToastProvider>
  );
}
