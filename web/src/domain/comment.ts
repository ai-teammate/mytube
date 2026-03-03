// Domain layer: entities and repository interface for video comments.
// No framework dependencies.

/** Author info embedded in a comment. */
export interface CommentAuthor {
  username: string;
  avatarUrl: string | null;
}

/** A single comment. */
export interface Comment {
  id: string;
  body: string;
  author: CommentAuthor;
  createdAt: string; // ISO-8601
}

/** Repository interface for video comments. */
export interface CommentRepository {
  listByVideoID(videoID: string): Promise<Comment[]>;
  create(videoID: string, body: string, token: string): Promise<Comment>;
  deleteComment(commentID: string, token: string): Promise<void>;
}
