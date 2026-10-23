-- Undo: ALTER TABLE "Comment" DROP COLUMN "editedAt";

-- AlterTable
ALTER TABLE "Comment" ADD COLUMN     "editedAt" TIMESTAMP(3);
