CREATE TABLE "memberships" (
  "org_id" INTEGER NOT NULL,
  "user_id" INTEGER NOT NULL,
  "role" TEXT NOT NULL,
  PRIMARY KEY ("org_id", "user_id")
)
