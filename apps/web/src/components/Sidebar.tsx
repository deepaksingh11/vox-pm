import { useState } from "react";
import { Folder, MoreHorizontal, Plus } from "lucide-react";
import { useStore } from "../hooks/useStore";
import { cn } from "../lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { RenameDialog } from "./RenameDialog";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";

export function Sidebar() {
  const projects = useStore((s) => s.projects);
  const tasks = useStore((s) => s.tasks);
  const selectedProjectId = useStore((s) => s.selectedProjectId);
  const setSelectedProject = useStore((s) => s.setSelectedProject);
  const deleteProject = useStore((s) => s.deleteProject);
  const createProject = useStore((s) => s.createProject);

  const [renameTarget, setRenameTarget] = useState<{ id: string; title: string } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState("");

  async function handleCreateSubmit() {
    await createProject(draft);
    setDraft("");
    setCreating(false);
  }

  return (
    <nav className="flex flex-col h-full py-4 overflow-y-auto scrollbar-thin">
      {/* New project — muted fallback action */}
      {creating ? (
        <div className="mx-2 flex items-center gap-2.5 px-2.5 py-2 rounded-md bg-accent/40">
          <Plus size={15} className="text-muted-foreground shrink-0" />
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { void handleCreateSubmit(); }
              else if (e.key === "Escape") { setDraft(""); setCreating(false); }
            }}
            onBlur={() => { setDraft(""); setCreating(false); }}
            placeholder="Project name…"
            className="flex-1 bg-transparent outline-none text-sm placeholder:text-muted-foreground/50"
          />
        </div>
      ) : (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => setCreating(true)}
              className="mx-2 flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm
                         text-muted-foreground/70 hover:bg-accent/40 hover:text-muted-foreground
                         transition-colors"
            >
              <Plus size={15} className="shrink-0" />
              <span className="flex-1 text-left">New project</span>
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">
            Voice is faster — try saying "create a project…"
          </TooltipContent>
        </Tooltip>
      )}

      {/* Projects section */}
      <div className="mt-5 mb-2 mx-3 flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-widest text-foreground/50">
          Projects
        </span>
        {projects.length > 0 && (
          <span className="text-[10px] font-semibold tabular-nums text-muted-foreground/40">
            {projects.length}
          </span>
        )}
      </div>

      {projects.length === 0 ? (
        <div className="mx-3 mt-1 rounded-lg border border-dashed border-border/50 px-3 py-4 flex flex-col items-center gap-2 text-center">
          <p className="text-[11px] text-muted-foreground/50 leading-relaxed">
            Hold the mic and say{" "}
            <span className="font-medium text-foreground/60">"create a project…"</span>
          </p>
        </div>
      ) : (
        projects.map((project) => {
          const openCount = tasks.filter(
            (t) => t.project_id === project.id && t.status === "open"
          ).length;
          const isActive = selectedProjectId === project.id;

          return (
            <div key={project.id} className="group relative mx-2">
              <button
                onClick={() => setSelectedProject(project.id)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm font-medium transition-colors pr-8",
                  isActive
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                )}
              >
                <Folder size={15} className={cn("shrink-0", isActive && "text-primary")} />
                <span className="flex-1 text-left truncate">{project.title}</span>
                {openCount > 0 && (
                  <span className="text-[10px] font-semibold text-muted-foreground/60 tabular-nums">
                    {openCount}
                  </span>
                )}
              </button>

              {/* Hover-reveal actions */}
              <div className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className="flex items-center justify-center w-6 h-6 rounded hover:bg-accent text-muted-foreground"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal size={13} />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        setRenameTarget({ id: project.id, title: project.title });
                      }}
                    >
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget({ id: project.id, title: project.title });
                      }}
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          );
        })
      )}

      {renameTarget && (
        <RenameDialog
          projectId={renameTarget.id}
          currentTitle={renameTarget.title}
          onClose={() => setRenameTarget(null)}
        />
      )}
      {deleteTarget && (
        <DeleteConfirmDialog
          title="Delete project"
          description={`"${deleteTarget.title}" and all its tasks will be unlinked. This cannot be undone.`}
          onConfirm={() => deleteProject(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </nav>
  );
}
