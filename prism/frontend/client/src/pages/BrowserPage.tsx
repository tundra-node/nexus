import { useState, useRef, useCallback, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Spinner } from "@/components/ui/spinner";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  Home,
  Globe,
  Bookmark as BookmarkIcon,
  ExternalLink,
  Trash2,
  Plus,
  BookmarkPlus,
  Check,
  X,
  ZoomIn,
  ZoomOut,
  Download,
  Code,
  XCircle,
  Loader2,
} from "lucide-react";
import {
  useBookmarks,
  saveBookmarks,
  proxyUrl,
  normalizeUrl,
  type Bookmark,
} from "@/hooks/useI2pdApi";
import { toast } from "sonner";


// ---------------------------------------------------------------------------
// Tab data model
// ---------------------------------------------------------------------------

interface TabData {
  id: string;
  url: string;
  currentUrl: string;
  history: string[];
  historyIdx: number;
  iframeKey: number;
}

let _tabCounter = 0;
function newTabId(): string {
  return `tab-${++_tabCounter}`;
}

function blankTab(): TabData {
  return {
    id: newTabId(),
    url: "",
    currentUrl: "",
    history: [],
    historyIdx: -1,
    iframeKey: 0,
  };
}

// ---------------------------------------------------------------------------
// HomePage
// ---------------------------------------------------------------------------

function HomePage({
  bookmarks,
  bmLoading,
  onNavigate,
}: {
  bookmarks: Bookmark[];
  bmLoading: boolean;
  onNavigate: (url: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight">Prism Browser</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Browse .i2p sites through the I2P network
        </p>
      </div>

      {/* Bookmarks */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <BookmarkIcon className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">Bookmarks</h2>
          {bmLoading && <Spinner className="h-3 w-3" />}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
          {bookmarks.map((bm, i) => (
            <Card
              key={i}
              className="cursor-pointer transition-colors hover:bg-muted/50"
              onClick={() => onNavigate(bm.url)}
            >
              <CardContent className="flex items-center gap-2 p-3">
                <ExternalLink className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                <span className="truncate text-xs font-medium">{bm.name}</span>
              </CardContent>
            </Card>
          ))}
          {bookmarks.length === 0 && !bmLoading && (
            <p className="col-span-full text-xs text-muted-foreground">
              No bookmarks yet. Add some using the bookmark button in the URL bar.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab helpers
// ---------------------------------------------------------------------------

function tabTitle(tab: TabData): string {
  if (!tab.currentUrl) return "New Tab";
  try {
    return new URL(tab.currentUrl).hostname;
  } catch {
    return tab.currentUrl;
  }
}

// ---------------------------------------------------------------------------
// BrowserPage
// ---------------------------------------------------------------------------

export default function BrowserPage() {
  const { bookmarks, loading: bmLoading, refetch: refetchBm } = useBookmarks();
  const [tabs, setTabs] = useState<TabData[]>([blankTab()]);
  const [activeTabId, setActiveTabId] = useState(tabs[0].id);
  const [editingBookmarks, setEditingBookmarks] = useState(false);
  const [editBookmarks, setEditBookmarks] = useState<Bookmark[]>([]);
  const [newBmName, setNewBmName] = useState("");
  const [newBmUrl, setNewBmUrl] = useState("");
  const [jsEnabled, setJsEnabled] = useState(false);
  const [zoom, setZoom] = useState(1);

  const activeTab = tabs.find((t) => t.id === activeTabId) ?? tabs[0];
  const iframeRefs = useRef<Map<string, HTMLIFrameElement | null>>(new Map());

  // Keep activeTabId valid when tabs change
  useEffect(() => {
    setActiveTabId((prev) => (!tabs.some((t) => t.id === prev) ? tabs[0]?.id : prev));
  }, [tabs]);

  // ---- Tab management ------------------------------------------------

  const switchTab = useCallback((id: string) => {
    setActiveTabId(id);
  }, []);

  const addTab = useCallback(() => {
    const t = blankTab();
    setTabs((prev) => [...prev, t]);
    setActiveTabId(t.id);
  }, []);

  const closeTab = useCallback((id: string) => {
    setTabs((prev) => {
      if (prev.length <= 1) {
        return [blankTab()];
      }
      return prev.filter((t) => t.id !== id);
    });
  }, []);

  // ---- Navigation helpers (operate on active tab via functional set) -

  const updateActiveTab = useCallback(
    (fn: (tab: TabData) => TabData) => {
      setTabs((prev) => {
        const idx = prev.findIndex((t) => t.id === activeTabId);
        if (idx < 0) return prev;
        const next = [...prev];
        next[idx] = fn(next[idx]);
        return next;
      });
    },
    [activeTabId],
  );

  const navigate = useCallback(
    (targetUrl: string) => {
      updateActiveTab((tab) => {
        const newHistory = tab.history.slice(0, tab.historyIdx + 1);
        newHistory.push(targetUrl);
        return {
          ...tab,
          url: targetUrl,
          currentUrl: targetUrl,
          history: newHistory,
          historyIdx: newHistory.length - 1,
          iframeKey: tab.iframeKey + 1,
        };
      });
    },
    [updateActiveTab],
  );

  const goHome = useCallback(() => {
    updateActiveTab((tab) => ({ ...tab, url: "", currentUrl: "" }));
  }, [updateActiveTab]);

  const goBack = useCallback(() => {
    updateActiveTab((tab) => {
      if (tab.historyIdx < 0) return tab;
      if (tab.historyIdx === 0) {
        return { ...tab, url: "", currentUrl: "" };
      }
      const idx = tab.historyIdx - 1;
      return {
        ...tab,
        historyIdx: idx,
        url: tab.history[idx],
        currentUrl: tab.history[idx],
        iframeKey: tab.iframeKey + 1,
      };
    });
  }, [updateActiveTab]);

  const goForward = useCallback(() => {
    updateActiveTab((tab) => {
      if (tab.historyIdx >= tab.history.length - 1) return tab;
      const idx = tab.historyIdx + 1;
      return {
        ...tab,
        historyIdx: idx,
        url: tab.history[idx],
        currentUrl: tab.history[idx],
        iframeKey: tab.iframeKey + 1,
      };
    });
  }, [updateActiveTab]);

  const refresh = useCallback(() => {
    updateActiveTab((tab) => {
      if (!tab.currentUrl) return tab;
      return { ...tab, iframeKey: tab.iframeKey + 1 };
    });
  }, [updateActiveTab]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const target = normalizeUrl(activeTab.url);
      if (!target) return;
      navigate(target);
    },
    [activeTab.url, navigate],
  );

  const setUrl = useCallback(
    (u: string) => {
      updateActiveTab((tab) => ({ ...tab, url: u }));
    },
    [updateActiveTab],
  );

  // ---- Download -----------------------------------------------------

  const downloadPage = useCallback(async () => {
    const url = activeTab.currentUrl;
    if (!url) return;
    try {
      const resp = await fetch(proxyUrl(url));
      const html = await resp.text();
      const blob = new Blob([html], { type: "text/html" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      const fname = url
        .replace(/^https?:\/\//, "")
        .replace(/[^a-z0-9]/gi, "_")
        .replace(/_+/g, "_")
        .replace(/^_|_$/g, "");
      a.download = `${fname || "page"}.html`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success("Page downloaded");
    } catch {
      toast.error("Failed to download page");
    }
  }, [activeTab.currentUrl]);

  // ---- Bookmark management ------------------------------------------

  const openBookmark = useCallback(
    (bm: Bookmark) => {
      navigate(bm.url);
    },
    [navigate],
  );

  const startEditBookmarks = () => {
    setEditBookmarks([...bookmarks]);
    setEditingBookmarks(true);
  };

  const saveEditBookmarks = async () => {
    await saveBookmarks(editBookmarks);
    await refetchBm();
    setEditingBookmarks(false);
    toast.success("Bookmarks saved");
  };

  const addBookmark = () => {
    if (!newBmName.trim() || !newBmUrl.trim()) return;
    const u = normalizeUrl(newBmUrl);
    if (!u) return;
    setEditBookmarks((prev) => [...prev, { name: newBmName.trim(), url: u }]);
    setNewBmName("");
    setNewBmUrl("");
  };

  const removeEditBookmark = (idx: number) => {
    setEditBookmarks((prev) => prev.filter((_, i) => i !== idx));
  };

  const bookmarkCurrentPage = async () => {
    const cu = activeTab.currentUrl;
    if (!cu) return;
    const exists = bookmarks.some((b) => b.url === cu);
    if (exists) {
      toast.info("Already bookmarked");
      return;
    }
    const name = cu.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    const next = [...bookmarks, { name, url: cu }];
    await saveBookmarks(next);
    await refetchBm();
    toast.success(`Bookmarked: ${name}`);
  };

  // ---- Zoom & JS ----------------------------------------------------

  const zoomIn = () => setZoom((z) => Math.min(z + 0.25, 3));
  const zoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.25));
  const zoomReset = () => setZoom(1);

  const toggleJs = () => {
    setJsEnabled((prev) => !prev);
    // Force iframe reload with new sandbox
    updateActiveTab((tab) => {
      if (!tab.currentUrl) return tab;
      return { ...tab, iframeKey: tab.iframeKey + 1 };
    });
  };

  const sandboxAttr = `allow-same-origin allow-forms${jsEnabled ? " allow-scripts" : ""}`;

  // ---- Render -------------------------------------------------------

  return (
    <div className="flex h-full flex-col">
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b border-border bg-muted/30 px-1 pt-1">
        <div className="flex flex-1 items-center gap-0 overflow-x-auto">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                className={`group flex max-w-[160px] cursor-pointer items-center gap-1 rounded-t-md px-2 py-1.5 text-xs transition-colors ${
                  isActive
                    ? "border-x border-t border-border bg-card text-foreground"
                    : "text-muted-foreground hover:bg-muted/50"
                }`}
                onClick={() => switchTab(tab.id)}
              >
                <Globe className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{tabTitle(tab)}</span>
                <button
                  className={`ml-auto flex h-4 w-4 items-center justify-center rounded-full transition-colors hover:bg-muted-foreground/20 ${
                    isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(tab.id);
                  }}
                >
                  <XCircle className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
        <Button variant="ghost" size="sm" className="h-7 w-7 flex-shrink-0" onClick={addTab} title="New tab">
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* URL bar */}
      <div className="flex items-center gap-1.5 border-b border-border bg-card px-2 py-1.5">
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={goBack} disabled={activeTab.historyIdx < 0}>
          <ArrowLeft className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={goForward}
          disabled={activeTab.historyIdx >= activeTab.history.length - 1}
        >
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={refresh} disabled={!activeTab.currentUrl}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={goHome} disabled={!activeTab.currentUrl}>
          <Home className="h-3.5 w-3.5" />
        </Button>

        <form onSubmit={handleSubmit} className="flex-1">
          <Input
            value={activeTab.url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Enter an .i2p URL..."
            className="h-7 font-mono text-xs"
          />
        </form>

        {/* Bookmark current page */}
        {activeTab.currentUrl && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={bookmarkCurrentPage} title="Bookmark this page">
            <BookmarkPlus className="h-3.5 w-3.5" />
          </Button>
        )}

        {/* Zoom controls */}
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomOut} title="Zoom out">
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <button
            className="min-w-[2.5rem] rounded px-1 text-[10px] tabular-nums text-muted-foreground hover:bg-muted"
            onClick={zoomReset}
            title="Reset zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomIn} title="Zoom in">
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* JS toggle */}
        <Button
          variant={jsEnabled ? "default" : "ghost"}
          size="sm"
          className={`h-7 gap-1 px-1.5 text-[10px] ${jsEnabled ? "" : "text-muted-foreground"}`}
          onClick={toggleJs}
          title={jsEnabled ? "JavaScript: ON" : "JavaScript: OFF"}
        >
          <Code className="h-3 w-3" />
          JS
        </Button>

        {/* Download */}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={downloadPage}
          disabled={!activeTab.currentUrl}
          title="Download page"
        >
          <Download className="h-3.5 w-3.5" />
        </Button>

        {/* Bookmark manager */}
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7">
              <BookmarkIcon className="h-3.5 w-3.5" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="absolute right-2 top-20 z-50 w-72 rounded-lg border bg-card shadow-lg">
            <Card className="border-0">
              <CardHeader className="pb-2 pt-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">Bookmarks</CardTitle>
                  {!editingBookmarks ? (
                    <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={startEditBookmarks}>
                      Edit
                    </Button>
                  ) : (
                    <Button variant="default" size="sm" className="h-6 text-xs" onClick={saveEditBookmarks}>
                      Save
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pb-3">
                {editingBookmarks ? (
                  <div className="space-y-2">
                    {editBookmarks.map((bm, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <Input
                          value={bm.name}
                          onChange={(e) => {
                            const next = [...editBookmarks];
                            next[i] = { ...next[i], name: e.target.value };
                            setEditBookmarks(next);
                          }}
                          className="h-7 text-xs"
                          placeholder="Name"
                        />
                        <Input
                          value={bm.url}
                          onChange={(e) => {
                            const next = [...editBookmarks];
                            next[i] = { ...next[i], url: e.target.value };
                            setEditBookmarks(next);
                          }}
                          className="h-7 flex-1 text-xs font-mono"
                          placeholder="URL"
                        />
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeEditBookmark(i)}>
                          <Trash2 className="h-3 w-3 text-destructive" />
                        </Button>
                      </div>
                    ))}
                    <div className="flex items-center gap-1">
                      <Input
                        value={newBmName}
                        onChange={(e) => setNewBmName(e.target.value)}
                        className="h-7 text-xs"
                        placeholder="Name"
                      />
                      <Input
                        value={newBmUrl}
                        onChange={(e) => setNewBmUrl(e.target.value)}
                        className="h-7 flex-1 text-xs font-mono"
                        placeholder="URL"
                      />
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={addBookmark}>
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {bookmarks.map((bm, i) => (
                      <Button
                        key={i}
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-xs"
                        onClick={() => openBookmark(bm)}
                      >
                        <ExternalLink className="mr-1.5 h-3 w-3" />
                        {bm.name}
                      </Button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      </div>

      {/* Content */}
      {activeTab.currentUrl ? (
        <div className="flex-1 overflow-auto bg-white">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={tab.id === activeTabId ? "block" : "hidden"}
              style={{ minHeight: "100%" }}
            >
              {tab.currentUrl && (
                <iframe
                  key={tab.iframeKey}
                  ref={(el) => { iframeRefs.current.set(tab.id, el); }}
                  src={proxyUrl(tab.currentUrl)}
                  style={{
                    width: `${zoom * 100}%`,
                    minHeight: `${zoom * 100}vh`,
                  }}
                  sandbox={sandboxAttr}
                  title={`I2P Browser - ${tabTitle(tab)}`}
                />
              )}
            </div>
          ))}
        </div>
      ) : (
        <HomePage bookmarks={bookmarks} bmLoading={bmLoading} onNavigate={navigate} />
      )}
    </div>
  );
}
