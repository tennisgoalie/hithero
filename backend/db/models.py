from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func

from backend.db.base import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True)
    school_name = Column(String)
    district = Column(String)
    county = Column(String)
    state = Column(String)


class NewUsers(Base):
    __tablename__ = "new_users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    state = Column(String)
    county = Column(String)
    district = Column(String)
    school = Column(String)
    phone_number = Column(String)
    password = Column(String)
    role = Column(String)
    report = Column(Integer)
    emailed = Column(Integer)


class RegisteredUsers(Base):
    __tablename__ = "registered_users"

    id = Column(Integer, primary_key=True)
    email = Column(String)
    phone_number = Column(String)
    password = Column(String)
    role = Column(String)
    createCount = Column(Integer)


class TeacherList(Base):
    __tablename__ = "teacher_list"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    state = Column(String)
    county = Column(String)
    district = Column(String)
    school = Column(String)
    regUserID = Column(Integer)
    wishlist_url = Column(String)
    about_me = Column(String)
    image_data = Column(LargeBinary)
    url_id = Column(String)
class Spotlight(Base):
    __tablename__ = "spotlight"

    id = Column(Integer, primary_key=True)
    token = Column(String)
    name = Column(String)
    state = Column(String)
    county = Column(String)
    district = Column(String)
    school = Column(String)
    image_data = Column(LargeBinary)


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("registered_users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    upvote_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("registered_users.id"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("forum_comments.id"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class PostVote(Base):
    __tablename__ = "post_votes"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("registered_users.id"), nullable=False)
    vote_type = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_user_vote"),)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    token = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Integer, default=0)


__all__ = [
    "ForumComment",
    "ForumPost",
    "NewUsers",
    "PasswordResetToken",
    "PostVote",
    "RegisteredUsers",
    "School",
    "Spotlight",
    "TeacherList",
]
