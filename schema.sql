drop table if exists user;
create table user (
  user_id integer primary key autoincrement,
  username text not null,
  password_hash text not null
);

drop table if exists stocks;
create table stocks (
  user_id integer not null,
  symbol text not null,
  shares integer not null,
  purchase_price float not null
);
