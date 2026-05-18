import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useStore } from "../hooks/useStore";

interface Props {
  projectId: string;
  currentTitle: string;
  onClose: () => void;
}

export function RenameDialog({ projectId, currentTitle, onClose }: Props) {
  const [title, setTitle] = useState(currentTitle);
  const [saving, setSaving] = useState(false);
  const renameProject = useStore((s) => s.renameProject);

  async function handleSave() {
    const trimmed = title.trim();
    if (!trimmed || trimmed === currentTitle) { onClose(); return; }
    setSaving(true);
    renameProject(projectId, trimmed);
    setSaving(false);
    onClose();
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Rename project</DialogTitle>
        </DialogHeader>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void handleSave(); if (e.key === "Escape") onClose(); }}
          autoFocus
        />
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} disabled={saving || !title.trim()}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
