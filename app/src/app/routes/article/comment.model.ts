import { Article } from './article.model';

export interface Comment {
  id: number;
  createdAt: Date;
  updatedAt: Date;
  editedAt: Date | null;
  body: string;
  authorId: number;
  article?: Article;
}
