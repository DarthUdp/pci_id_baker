create table pci_vendor
(
    vendor       integer
        constraint pci_vendor_pk
            primary key,
    name     text              not null,
    clean_name  text default null,
    wrong_id tinyint    default 0 not null
);

create table pci_dev
(
    vendor   integer not null
        references pci_vendor,
    device         integer,
    name text    not null
);

create table pci_sub_dev
(
    parent_device  integer
        references pci_dev,
    subvendor      integer,
    subdevice      integer,
    subsystem_name text
);

create table pci_class
(
    class integer constraint pci_class_pk primary key,
    class_name text
);

create table pci_subclass
(
    parent_class integer references pci_class,
    subclass integer,
    subclass_name text
);

create table pci_prog_if
(
    parent_subclass integer references pci_subclass,
    prog_if integer,
    prog_if_name text
);
