import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import Home from "@/pages/Home";
import BrowserPage from "@/pages/BrowserPage";
import AddressbookPage from "@/pages/AddressbookPage";
import { Router, Route, Switch, useLocation } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import { Button } from "@/components/ui/button";
import { LayoutDashboard, Globe, BookmarkIcon } from "lucide-react";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/browser", label: "Browser", icon: Globe },
  { path: "/addressbook", label: "Addressbook", icon: BookmarkIcon },
];

function Sidebar() {
  const [location, setLocation] = useLocation();

  return (
    <aside className="flex w-14 flex-col items-center gap-2 border-r border-border bg-card py-4">
      <div className="mb-2 text-[10px] font-bold tracking-wider text-muted-foreground">
        AE
      </div>
      {navItems.map((item) => (
        <Button
          key={item.path}
          variant={location === item.path ? "default" : "ghost"}
          size="icon"
          className="h-9 w-9"
          onClick={() => setLocation(item.path)}
          title={item.label}
        >
          <item.icon className="h-4 w-4" />
        </Button>
      ))}
    </aside>
  );
}

function Router_() {
  return (
    <Router base="/dashboard">
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Switch>
            <Route path={"/"} component={Home} />
            <Route path={"/browser"} component={BrowserPage} />
            <Route path={"/addressbook"} component={AddressbookPage} />
            <Route component={NotFound} />
          </Switch>
        </main>
      </div>
    </Router>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark" switchable>
        <TooltipProvider>
          <Toaster />
          <Router_ />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
