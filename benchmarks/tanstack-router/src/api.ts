export type Post = { id: string; title: string; body: string };

const posts: Post[] = [
  { id: "1", title: "First post", body: "Hello from the first post." },
  { id: "2", title: "Second post", body: "More words in the second." },
  { id: "3", title: "Third post", body: "The third and last." },
];

export async function fetchPosts(): Promise<Post[]> {
  return posts;
}

export async function fetchPost(id: string): Promise<Post> {
  const post = posts.find((p) => p.id === id);
  if (!post) throw new Error(`post ${id} not found`);
  return post;
}
